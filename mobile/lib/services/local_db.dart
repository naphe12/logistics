import "dart:convert";

import "package:path/path.dart";
import "package:sqflite/sqflite.dart";

class LocalDb {
  static final LocalDb instance = LocalDb._internal();
  LocalDb._internal();

  Database? _db;

  String _newClientActionId() {
    final now = DateTime.now().microsecondsSinceEpoch;
    final rand = now % 100000;
    return "m-$now-$rand";
  }

  Future<Database> get database async {
    if (_db != null) return _db!;
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, "logix_mobile.db");
    _db = await openDatabase(
      path,
      version: 4,
      onCreate: (db, version) async {
        await db.execute("""
          CREATE TABLE shipments (
            id TEXT PRIMARY KEY,
            shipment_no TEXT,
            status TEXT,
            sender_phone TEXT,
            receiver_name TEXT,
            receiver_phone TEXT,
            updated_at TEXT,
            synced_at TEXT
          )
        """);
        await db.execute("""
          CREATE TABLE offline_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_action_id TEXT NOT NULL UNIQUE,
            action_type TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            client_version TEXT,
            conflict_policy TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        """);
        await db.execute("""
          CREATE TABLE sync_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_action_id TEXT NOT NULL UNIQUE,
            action_type TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            reason TEXT,
            server_snapshot_json TEXT,
            created_at TEXT NOT NULL
          )
        """);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await db.execute(
            "ALTER TABLE offline_actions ADD COLUMN client_action_id TEXT",
          );
          await db.execute(
            "UPDATE offline_actions SET client_action_id = 'legacy-' || id WHERE client_action_id IS NULL",
          );
          await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_offline_actions_client_action_id ON offline_actions(client_action_id)",
          );
        }
        if (oldVersion < 3) {
          await db.execute(
            "ALTER TABLE offline_actions ADD COLUMN client_version TEXT",
          );
          await db.execute(
            "ALTER TABLE offline_actions ADD COLUMN conflict_policy TEXT",
          );
        }
        if (oldVersion < 4) {
          await db.execute("""
            CREATE TABLE IF NOT EXISTS sync_conflicts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_action_id TEXT NOT NULL UNIQUE,
              action_type TEXT NOT NULL,
              method TEXT NOT NULL,
              path TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              reason TEXT,
              server_snapshot_json TEXT,
              created_at TEXT NOT NULL
            )
          """);
        }
      },
    );
    return _db!;
  }

  Future<void> upsertShipmentFromApi(Map<String, dynamic> row) async {
    final db = await database;
    final shipmentId = row["id"]?.toString() ?? "";
    if (shipmentId.isEmpty) return;
    await db.insert("shipments", {
      "id": shipmentId,
      "shipment_no": row["shipment_no"]?.toString(),
      "status": row["status"]?.toString(),
      "sender_phone": row["sender_phone"]?.toString(),
      "receiver_name": row["receiver_name"]?.toString(),
      "receiver_phone": row["receiver_phone"]?.toString(),
      "updated_at":
          row["server_version"]?.toString() ??
          row["updated_at"]?.toString() ??
          DateTime.now().toIso8601String(),
      "synced_at": DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> saveLocalShipmentDraft({
    required String localId,
    required String senderPhone,
    required String receiverName,
    required String receiverPhone,
  }) async {
    final db = await database;
    await db.insert("shipments", {
      "id": localId,
      "shipment_no": "LOCAL-$localId",
      "status": "pending_sync",
      "sender_phone": senderPhone,
      "receiver_name": receiverName,
      "receiver_phone": receiverPhone,
      "updated_at": DateTime.now().toIso8601String(),
      "synced_at": null,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<Map<String, dynamic>>> listShipments() async {
    final db = await database;
    return db.query("shipments", orderBy: "updated_at DESC");
  }

  Future<String?> findMatchingPendingDraftId({
    required String senderPhone,
    required String receiverName,
    required String receiverPhone,
  }) async {
    final db = await database;
    final rows = await db.query(
      "shipments",
      where:
          "status = ? AND sender_phone = ? AND receiver_name = ? AND receiver_phone = ?",
      whereArgs: ["pending_sync", senderPhone, receiverName, receiverPhone],
      orderBy: "updated_at DESC",
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return rows.first["id"]?.toString();
  }

  Future<void> deleteShipmentById(String shipmentId) async {
    final db = await database;
    await db.delete("shipments", where: "id = ?", whereArgs: [shipmentId]);
  }

  Future<Map<String, dynamic>?> getShipmentById(String shipmentId) async {
    final db = await database;
    final rows = await db.query(
      "shipments",
      where: "id = ?",
      whereArgs: [shipmentId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return rows.first;
  }

  Future<int> queueAction({
    required String actionType,
    required String method,
    required String path,
    required Map<String, dynamic> payload,
    String? clientVersion,
    String? conflictPolicy,
  }) async {
    final db = await database;
    return db.insert("offline_actions", {
      "client_action_id": _newClientActionId(),
      "action_type": actionType,
      "method": method.toUpperCase(),
      "path": path,
      "client_version": clientVersion,
      "conflict_policy": conflictPolicy,
      "payload_json": jsonEncode(payload),
      "created_at": DateTime.now().toIso8601String(),
      "attempts": 0,
      "last_error": null,
    });
  }

  Future<List<Map<String, dynamic>>> listQueuedActions() async {
    final db = await database;
    return db.query("offline_actions", orderBy: "id ASC");
  }

  Future<void> deleteQueuedAction(int id) async {
    final db = await database;
    await db.delete("offline_actions", where: "id = ?", whereArgs: [id]);
  }

  Future<void> markQueuedActionFailed(int id, String error) async {
    final db = await database;
    await db.rawUpdate(
      "UPDATE offline_actions SET attempts = attempts + 1, last_error = ? WHERE id = ?",
      [error, id],
    );
  }

  Future<void> resetQueuedActionFailure(int id) async {
    final db = await database;
    await db.rawUpdate(
      "UPDATE offline_actions SET attempts = 0, last_error = NULL WHERE id = ?",
      [id],
    );
  }

  Future<Map<String, int>> queueStats() async {
    final db = await database;
    final rows = await db.rawQuery(
      "SELECT COUNT(*) as total, SUM(CASE WHEN attempts > 0 THEN 1 ELSE 0 END) as failed FROM offline_actions",
    );
    final first = rows.isEmpty ? <String, Object?>{} : rows.first;
    return {
      "total": (first["total"] as int?) ?? 0,
      "failed": (first["failed"] as int?) ?? 0,
    };
  }

  Future<void> upsertSyncConflict({
    required String clientActionId,
    required String actionType,
    required String method,
    required String path,
    required Map<String, dynamic> payload,
    String? reason,
    Map<String, dynamic>? serverSnapshot,
  }) async {
    final db = await database;
    await db.insert("sync_conflicts", {
      "client_action_id": clientActionId,
      "action_type": actionType,
      "method": method.toUpperCase(),
      "path": path,
      "payload_json": jsonEncode(payload),
      "reason": reason,
      "server_snapshot_json": serverSnapshot == null
          ? null
          : jsonEncode(serverSnapshot),
      "created_at": DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<Map<String, dynamic>>> listSyncConflicts({
    int limit = 100,
  }) async {
    final db = await database;
    return db.query("sync_conflicts", orderBy: "id DESC", limit: limit);
  }

  Future<void> deleteSyncConflict(String clientActionId) async {
    final db = await database;
    await db.delete(
      "sync_conflicts",
      where: "client_action_id = ?",
      whereArgs: [clientActionId],
    );
  }

  Map<String, dynamic> decodeActionPayload(Map<String, dynamic> action) {
    final raw = action["payload_json"]?.toString() ?? "{}";
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) return decoded;
    return <String, dynamic>{};
  }
}
