import "package:connectivity_plus/connectivity_plus.dart";
import "package:shared_preferences/shared_preferences.dart";

import "api_client.dart";
import "local_db.dart";

class SyncResult {
  final bool online;
  final int pushed;
  final int pushFailed;
  final int pulled;
  final int conflicts;

  const SyncResult({
    required this.online,
    required this.pushed,
    required this.pushFailed,
    required this.pulled,
    required this.conflicts,
  });
}

class SyncService {
  final ApiClient apiClient;
  final LocalDb localDb;
  static const _kShipmentSyncCursor = "shipment_sync_cursor_v1";

  SyncService({required this.apiClient, required this.localDb});

  Future<String?> _loadShipmentCursor() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_kShipmentSyncCursor);
  }

  Future<void> _saveShipmentCursor(String cursor) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kShipmentSyncCursor, cursor);
  }

  Future<void> _reconcileCreatedShipment(
    Map<String, dynamic> actionPayload,
    dynamic responseData,
  ) async {
    if (responseData is! Map) return;
    final created = Map<String, dynamic>.from(responseData);
    final senderPhone = actionPayload["sender_phone"]?.toString() ?? "";
    final receiverName = actionPayload["receiver_name"]?.toString() ?? "";
    final receiverPhone = actionPayload["receiver_phone"]?.toString() ?? "";
    if (senderPhone.isEmpty || receiverName.isEmpty || receiverPhone.isEmpty) {
      return;
    }
    final draftId = await localDb.findMatchingPendingDraftId(
      senderPhone: senderPhone,
      receiverName: receiverName,
      receiverPhone: receiverPhone,
    );
    if (draftId != null && draftId.isNotEmpty) {
      await localDb.deleteShipmentById(draftId);
    }
    await localDb.upsertShipmentFromApi(created);
  }

  Future<SyncResult> syncAll() async {
    final connectivity = await Connectivity().checkConnectivity();
    final hasNetwork = connectivity.any((r) => r != ConnectivityResult.none);
    if (!hasNetwork) {
      return const SyncResult(
        online: false,
        pushed: 0,
        pushFailed: 0,
        pulled: 0,
        conflicts: 0,
      );
    }

    int pushed = 0;
    int pushFailed = 0;
    int pulled = 0;
    int conflicts = 0;

    final queued = await localDb.listQueuedActions();
    if (queued.isNotEmpty) {
      try {
        final batchActions = queued.map((item) {
          final payload = localDb.decodeActionPayload(item);
          final fallbackClientActionId = "legacy-${item["id"]}";
          return <String, dynamic>{
            "client_action_id":
                item["client_action_id"]?.toString() ?? fallbackClientActionId,
            "action_type": item["action_type"]?.toString() ?? "unknown",
            "method": item["method"]?.toString() ?? "POST",
            "path": item["path"]?.toString() ?? "/",
            "client_version": item["client_version"]?.toString(),
            "conflict_policy": item["conflict_policy"]?.toString(),
            "payload": payload,
          };
        }).toList();

        final batchResponse = await apiClient.syncPush(actions: batchActions);
        final results =
            (batchResponse["results"] as List<dynamic>? ?? const []);
        final resultById = <String, Map<String, dynamic>>{};
        for (final row in results) {
          if (row is Map) {
            final data = Map<String, dynamic>.from(row);
            final cid = data["client_action_id"]?.toString();
            if (cid != null && cid.isNotEmpty) {
              resultById[cid] = data;
            }
          }
        }

        for (final item in queued) {
          final id = item["id"] as int? ?? 0;
          final payload = localDb.decodeActionPayload(item);
          final clientActionId =
              item["client_action_id"]?.toString() ?? "legacy-$id";
          final result = resultById[clientActionId];
          final status = result?["status"]?.toString() ?? "failed";
          if (status == "applied" || status == "replayed") {
            if (item["action_type"]?.toString() == "create_shipment") {
              await _reconcileCreatedShipment(payload, result?["data"]);
            }
            await localDb.deleteQueuedAction(id);
            pushed += 1;
          } else if (status.startsWith("conflict_")) {
            final data = result?["data"];
            Map<String, dynamic>? serverSnapshot;
            if (data is Map) {
              final server = data["server"];
              if (server is Map) {
                serverSnapshot = Map<String, dynamic>.from(server);
                await localDb.upsertShipmentFromApi(serverSnapshot);
              }
            }
            await localDb.upsertSyncConflict(
              clientActionId: clientActionId,
              actionType: item["action_type"]?.toString() ?? "unknown",
              method: item["method"]?.toString() ?? "POST",
              path: item["path"]?.toString() ?? "/",
              payload: payload,
              reason: data is Map
                  ? data["message"]?.toString()
                  : "sync_conflict",
              serverSnapshot: serverSnapshot,
            );
            await localDb.deleteQueuedAction(id);
            pushFailed += 1;
            conflicts += 1;
          } else {
            await localDb.markQueuedActionFailed(
              id,
              result?["error"]?.toString() ?? "sync_push_failed",
            );
            pushFailed += 1;
          }
        }
      } catch (_) {
        for (final item in queued) {
          final id = item["id"] as int? ?? 0;
          final method = item["method"]?.toString() ?? "POST";
          final path = item["path"]?.toString() ?? "/";
          final payload = localDb.decodeActionPayload(item);
          try {
            final responseData = await apiClient.rawRequest(
              method: method,
              path: path,
              data: payload,
            );
            if (item["action_type"]?.toString() == "create_shipment") {
              await _reconcileCreatedShipment(payload, responseData);
            }
            await localDb.deleteQueuedAction(id);
            pushed += 1;
          } catch (e) {
            await localDb.markQueuedActionFailed(id, e.toString());
            pushFailed += 1;
          }
        }
      }
    }

    try {
      String? cursor = await _loadShipmentCursor();
      int pages = 0;
      while (pages < 5) {
        final delta = await apiClient.syncPullShipments(
          sinceIso: cursor,
          limit: 200,
        );
        final items = (delta["items"] as List<dynamic>? ?? const []);
        for (final row in items) {
          await localDb.upsertShipmentFromApi(
            Map<String, dynamic>.from(row as Map),
          );
          pulled += 1;
        }
        final nextCursor = delta["next_cursor"]?.toString();
        if (nextCursor != null && nextCursor.isNotEmpty) {
          cursor = nextCursor;
          await _saveShipmentCursor(nextCursor);
        }
        pages += 1;
        if (items.isEmpty) break;
      }
    } catch (_) {
      try {
        final remoteShipments = await apiClient.myShipments(limit: 150);
        for (final row in remoteShipments) {
          await localDb.upsertShipmentFromApi(row);
        }
        pulled = remoteShipments.length;
      } catch (_) {
        // Keep offline data untouched if pull fails.
      }
    }

    return SyncResult(
      online: true,
      pushed: pushed,
      pushFailed: pushFailed,
      pulled: pulled,
      conflicts: conflicts,
    );
  }
}
