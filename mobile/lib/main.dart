import "dart:async";

import "package:connectivity_plus/connectivity_plus.dart";
import "package:dio/dio.dart";
import "package:flutter/material.dart";

import "services/api_client.dart";
import "services/local_db.dart";
import "services/session_store.dart";
import "services/sync_service.dart";
import "ui/app_theme.dart";

void main() {
  runApp(const LogixMobileApp());
}

class LogixMobileApp extends StatefulWidget {
  const LogixMobileApp({super.key});

  @override
  State<LogixMobileApp> createState() => _LogixMobileAppState();
}

class _LogixMobileAppState extends State<LogixMobileApp> {
  final _api = ApiClient();
  final _db = LocalDb.instance;
  final _sessionStore = SessionStore();
  late final SyncService _syncService = SyncService(
    apiClient: _api,
    localDb: _db,
  );

  bool _booting = true;
  String _accessToken = "";
  String _phone = "";
  String _userType = "customer";

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await _db.database;
    final saved = await _sessionStore.load();
    if (saved != null) {
      _accessToken = saved.accessToken;
      _phone = saved.phone;
      _userType = saved.userType;
      _api.setAccessToken(saved.accessToken);
      try {
        final me = await _api.me();
        _userType = me["user_type"]?.toString() ?? _userType;
      } catch (_) {
        await _sessionStore.clear();
        _accessToken = "";
      }
    }
    if (!mounted) return;
    setState(() => _booting = false);
  }

  Future<void> _onLoggedIn({
    required String accessToken,
    required String refreshToken,
    required String phone,
  }) async {
    _api.setAccessToken(accessToken);
    var userType = "customer";
    try {
      final me = await _api.me();
      userType = me["user_type"]?.toString() ?? userType;
    } catch (_) {}
    await _sessionStore.save(
      SessionData(
        accessToken: accessToken,
        refreshToken: refreshToken,
        phone: phone,
        userType: userType,
      ),
    );
    if (!mounted) return;
    setState(() {
      _accessToken = accessToken;
      _phone = phone;
      _userType = userType;
    });
  }

  Future<void> _logout() async {
    await _sessionStore.clear();
    _api.clearAccessToken();
    if (!mounted) return;
    setState(() {
      _accessToken = "";
      _phone = "";
      _userType = "customer";
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "Logix Mobile",
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: _booting
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : (_accessToken.isEmpty
                ? LoginScreen(apiClient: _api, onLoggedIn: _onLoggedIn)
                : HomeScreen(
                    apiClient: _api,
                    localDb: _db,
                    syncService: _syncService,
                    onLogout: _logout,
                    phone: _phone,
                    userType: _userType,
                  )),
    );
  }
}

class LoginScreen extends StatefulWidget {
  final ApiClient apiClient;
  final Future<void> Function({
    required String accessToken,
    required String refreshToken,
    required String phone,
  })
  onLoggedIn;

  const LoginScreen({
    super.key,
    required this.apiClient,
    required this.onLoggedIn,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneCtrl = TextEditingController(text: "+257");
  final _otpCtrl = TextEditingController();
  bool _busy = false;
  String _message = "";
  String _error = "";

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }

  Future<void> _requestOtp() async {
    setState(() {
      _busy = true;
      _error = "";
      _message = "";
    });
    try {
      await widget.apiClient.requestOtp(_phoneCtrl.text.trim());
      if (!mounted) return;
      setState(
        () => _message = "OTP envoye. Verifie le SMS puis saisis le code.",
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _verifyOtp() async {
    setState(() {
      _busy = true;
      _error = "";
      _message = "";
    });
    try {
      final res = await widget.apiClient.verifyOtp(
        _phoneCtrl.text.trim(),
        _otpCtrl.text.trim(),
      );
      await widget.onLoggedIn(
        accessToken: res["access_token"]?.toString() ?? "",
        refreshToken: res["refresh_token"]?.toString() ?? "",
        phone: _phoneCtrl.text.trim(),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _devLogin() async {
    setState(() {
      _busy = true;
      _error = "";
      _message = "";
    });
    try {
      final res = await widget.apiClient.devLogin(_phoneCtrl.text.trim());
      await widget.onLoggedIn(
        accessToken: res["access_token"]?.toString() ?? "",
        refreshToken: res["refresh_token"]?.toString() ?? "",
        phone: _phoneCtrl.text.trim(),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = "Dev login refuse (normal en prod): $e");
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: AppDecor.heroGradient,
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(18),
              child: Container(
                decoration: AppDecor.glassCard,
                padding: const EdgeInsets.all(18),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: const [
                        CircleAvatar(
                          radius: 20,
                          backgroundColor: Color(0x14155E75),
                          child: Icon(
                            Icons.local_shipping,
                            color: AppTheme.brandSecondary,
                          ),
                        ),
                        SizedBox(width: 10),
                        Text(
                          "Logix Mobile",
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      "Connexion securisee OTP avec mode offline-first.",
                      style: TextStyle(
                        color: Colors.black.withValues(alpha: 0.72),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _phoneCtrl,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.phone_iphone_outlined),
                        labelText: "Telephone E164",
                        hintText: "+2577XXXXXXX",
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _otpCtrl,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.password_outlined),
                        labelText: "Code OTP",
                        hintText: "1234",
                      ),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        FilledButton.icon(
                          onPressed: _busy ? null : _requestOtp,
                          icon: const Icon(Icons.sms_outlined),
                          label: const Text("Demander OTP"),
                        ),
                        FilledButton.icon(
                          onPressed: _busy ? null : _verifyOtp,
                          icon: const Icon(Icons.verified_outlined),
                          label: const Text("Verifier OTP"),
                        ),
                        OutlinedButton.icon(
                          onPressed: _busy ? null : _devLogin,
                          icon: const Icon(Icons.developer_mode_outlined),
                          label: const Text("Dev Login"),
                        ),
                      ],
                    ),
                    if (_busy) ...[
                      const SizedBox(height: 10),
                      const LinearProgressIndicator(minHeight: 3),
                    ],
                    if (_message.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(
                        _message,
                        style: const TextStyle(color: AppTheme.brandPrimary),
                      ),
                    ],
                    if (_error.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(_error, style: const TextStyle(color: Colors.red)),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  final ApiClient apiClient;
  final LocalDb localDb;
  final SyncService syncService;
  final Future<void> Function() onLogout;
  final String phone;
  final String userType;

  const HomeScreen({
    super.key,
    required this.apiClient,
    required this.localDb,
    required this.syncService,
    required this.onLogout,
    required this.phone,
    required this.userType,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tabIndex = 0;
  bool _syncing = false;
  bool _online = false;
  String _syncMessage = "";
  List<Map<String, dynamic>> _shipments = const [];
  List<Map<String, dynamic>> _queuedActions = const [];
  List<Map<String, dynamic>> _syncConflicts = const [];
  List<Map<String, dynamic>> _serverSyncConflictIncidents = const [];
  List<Map<String, dynamic>> _adminIncidents = const [];
  List<Map<String, dynamic>> _adminClaims = const [];
  List<Map<String, dynamic>> _opsAlerts = const [];
  List<Map<String, dynamic>> _opsErrors = const [];
  Map<String, dynamic>? _smsWorkerStatus;
  Map<String, dynamic>? _lastAutoDetectResult;
  Map<String, dynamic>? _lastNotifyCriticalResult;
  List<Map<String, dynamic>> _payments = const [];
  List<Map<String, dynamic>> _commissions = const [];
  List<String> _paymentStatuses = const [];
  List<Map<String, dynamic>> _relays = const [];
  List<Map<String, dynamic>> _agents = const [];
  List<Map<String, dynamic>> _relayAgents = const [];
  Map<String, dynamic>? _relayCapacity;
  List<Map<String, dynamic>> _trips = const [];
  List<Map<String, dynamic>> _tripManifestShipments = const [];
  String _selectedTripId = "";
  String _syncConflictStatusFilter = "open";
  String _incidentStatusFilter = "all";
  String _claimStatusFilter = "all";
  String _paymentStatusFilter = "all";
  String _paymentStage = "at_send";
  String _incidentTypeCreate = "delayed";
  String _claimStatusUpdate = "reviewing";
  String _selectedRelayId = "";
  String _editingRelayId = "";
  String _assignAgentId = "";
  Map<String, int> _queueStats = const {"total": 0, "failed": 0};
  Map<String, dynamic>? _overview;
  Timer? _autoSyncTimer;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;

  final _senderPhoneCtrl = TextEditingController();
  final _receiverNameCtrl = TextEditingController();
  final _receiverPhoneCtrl = TextEditingController();

  final _pickupShipmentIdCtrl = TextEditingController();
  final _pickupCodeCtrl = TextEditingController();
  final _pickupRelayIdCtrl = TextEditingController();
  final _syncIncidentShipmentFilterCtrl = TextEditingController();
  final _relayCodeCtrl = TextEditingController();
  final _relayNameCtrl = TextEditingController();
  final _relayTypeCtrl = TextEditingController(text: "relay");
  final _relayOpeningHoursCtrl = TextEditingController();
  final _relayCapacityCtrl = TextEditingController();
  final _tripRouteIdCtrl = TextEditingController();
  final _tripVehicleIdCtrl = TextEditingController();
  final _tripStatusCtrl = TextEditingController(text: "planned");
  final _manifestShipmentIdCtrl = TextEditingController();
  final _tripScanRelayIdCtrl = TextEditingController();
  final _tripVehicleCapacityCtrl = TextEditingController(text: "50");
  final _incidentShipmentIdCtrl = TextEditingController();
  final _incidentDescriptionCtrl = TextEditingController();
  final _claimIncidentIdCtrl = TextEditingController();
  final _claimShipmentIdCtrl = TextEditingController();
  final _claimAmountCtrl = TextEditingController();
  final _claimReasonCtrl = TextEditingController();
  final _claimIdUpdateCtrl = TextEditingController();
  final _claimResolutionNoteCtrl = TextEditingController();
  final _paymentShipmentIdCtrl = TextEditingController();
  final _paymentAmountCtrl = TextEditingController();
  final _paymentPayerPhoneCtrl = TextEditingController();
  final _paymentProviderCtrl = TextEditingController(text: "lumicash");
  final _paymentActionIdCtrl = TextEditingController();
  final _paymentExternalRefCtrl = TextEditingController();
  final _paymentFailReasonCtrl = TextEditingController(
    text: "payment_provider_error",
  );
  final _paymentRefundReasonCtrl = TextEditingController(text: "claim_refund");
  final _paymentFilterShipmentCtrl = TextEditingController();
  final _paymentFilterPayerCtrl = TextEditingController();
  final _opsDelayedHoursCtrl = TextEditingController(text: "48");
  final _opsRelayWarnCtrl = TextEditingController(text: "0.9");
  bool _relayIsActive = true;

  @override
  void initState() {
    super.initState();
    _tabIndex = _defaultTabForRole(widget.userType);
    _senderPhoneCtrl.text = widget.phone;
    _reloadLocalState();
    if (widget.userType == "admin") {
      unawaited(_loadBackofficeOverview());
      unawaited(_loadOpsMonitoringData());
      unawaited(_loadServerSyncConflictIncidents());
      unawaited(_loadPaymentAdminData());
      unawaited(_loadIncidentClaimAdminData());
      unawaited(_loadRelayAdminData());
      unawaited(_loadTransportData());
    }
    _initConnectivity();
    _startAutoSyncTimer();
  }

  int _defaultTabForRole(String role) {
    return 0;
  }

  bool get _isAdmin => widget.userType == "admin";

  bool get _isAgentLike =>
      widget.userType == "agent" || widget.userType == "hub";

  List<Widget> _rolePages() {
    if (_isAdmin) {
      return [_buildAdminTab()];
    }
    if (_isAgentLike) {
      return [_buildAgentTab()];
    }
    return [_buildCustomerTab()];
  }

  List<NavigationDestination> _roleDestinations() {
    if (_isAdmin) {
      return const [
        NavigationDestination(
          icon: Icon(Icons.admin_panel_settings_outlined),
          selectedIcon: Icon(Icons.admin_panel_settings),
          label: "Admin",
        ),
      ];
    }
    if (_isAgentLike) {
      return const [
        NavigationDestination(
          icon: Icon(Icons.badge_outlined),
          selectedIcon: Icon(Icons.badge),
          label: "Agent",
        ),
      ];
    }
    return const [
      NavigationDestination(
        icon: Icon(Icons.person_outline),
        selectedIcon: Icon(Icons.person),
        label: "Client",
      ),
    ];
  }

  Future<void> _initConnectivity() async {
    final initial = await Connectivity().checkConnectivity();
    if (!mounted) return;
    setState(() => _online = initial.any((r) => r != ConnectivityResult.none));
    if (_online) unawaited(_syncNow(silent: true));

    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      final hasNetwork = results.any((r) => r != ConnectivityResult.none);
      if (!mounted) return;
      final wasOnline = _online;
      setState(() => _online = hasNetwork);
      if (!wasOnline && hasNetwork) {
        unawaited(_syncNow(silent: true));
      }
    });
  }

  void _startAutoSyncTimer() {
    _autoSyncTimer = Timer.periodic(const Duration(seconds: 45), (_) {
      if (_online) {
        unawaited(_syncNow(silent: true));
      }
    });
  }

  @override
  void dispose() {
    _autoSyncTimer?.cancel();
    _connectivitySub?.cancel();
    _senderPhoneCtrl.dispose();
    _receiverNameCtrl.dispose();
    _receiverPhoneCtrl.dispose();
    _pickupShipmentIdCtrl.dispose();
    _pickupCodeCtrl.dispose();
    _pickupRelayIdCtrl.dispose();
    _syncIncidentShipmentFilterCtrl.dispose();
    _relayCodeCtrl.dispose();
    _relayNameCtrl.dispose();
    _relayTypeCtrl.dispose();
    _relayOpeningHoursCtrl.dispose();
    _relayCapacityCtrl.dispose();
    _tripRouteIdCtrl.dispose();
    _tripVehicleIdCtrl.dispose();
    _tripStatusCtrl.dispose();
    _manifestShipmentIdCtrl.dispose();
    _tripScanRelayIdCtrl.dispose();
    _tripVehicleCapacityCtrl.dispose();
    _incidentShipmentIdCtrl.dispose();
    _incidentDescriptionCtrl.dispose();
    _claimIncidentIdCtrl.dispose();
    _claimShipmentIdCtrl.dispose();
    _claimAmountCtrl.dispose();
    _claimReasonCtrl.dispose();
    _claimIdUpdateCtrl.dispose();
    _claimResolutionNoteCtrl.dispose();
    _paymentShipmentIdCtrl.dispose();
    _paymentAmountCtrl.dispose();
    _paymentPayerPhoneCtrl.dispose();
    _paymentProviderCtrl.dispose();
    _paymentActionIdCtrl.dispose();
    _paymentExternalRefCtrl.dispose();
    _paymentFailReasonCtrl.dispose();
    _paymentRefundReasonCtrl.dispose();
    _paymentFilterShipmentCtrl.dispose();
    _paymentFilterPayerCtrl.dispose();
    _opsDelayedHoursCtrl.dispose();
    _opsRelayWarnCtrl.dispose();
    super.dispose();
  }

  Future<void> _reloadLocalState() async {
    final shipments = await widget.localDb.listShipments();
    final queued = await widget.localDb.listQueuedActions();
    final stats = await widget.localDb.queueStats();
    final conflicts = await widget.localDb.listSyncConflicts(limit: 50);
    if (!mounted) return;
    setState(() {
      _shipments = shipments;
      _queuedActions = queued;
      _queueStats = stats;
      _syncConflicts = conflicts;
    });
  }

  Future<void> _syncNow({bool silent = false}) async {
    if (_syncing) return;
    if (!silent) {
      setState(() {
        _syncMessage = "";
      });
    }
    setState(() => _syncing = true);
    try {
      final res = await widget.syncService.syncAll();
      await _reloadLocalState();
      if (!mounted) return;
      setState(() {
        _online = res.online;
        _syncMessage = res.online
            ? "Sync OK: push ${res.pushed}, fail ${res.pushFailed}, conflicts ${res.conflicts}, pull ${res.pulled}"
            : "Hors ligne: queue locale active.";
      });
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  bool _isNetworkError(Object e) {
    if (e is DioException) {
      return e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout;
    }
    final msg = e.toString().toLowerCase();
    return msg.contains("socketexception") ||
        msg.contains("network") ||
        msg.contains("timed out");
  }

  Future<void> _queueOfflineAction({
    required String actionType,
    required String method,
    required String path,
    required Map<String, dynamic> payload,
    String? clientVersion,
    String? conflictPolicy,
    String? message,
  }) async {
    await widget.localDb.queueAction(
      actionType: actionType,
      method: method,
      path: path,
      payload: payload,
      clientVersion: clientVersion,
      conflictPolicy: conflictPolicy,
    );
    await _reloadLocalState();
    if (!mounted) return;
    setState(
      () => _syncMessage =
          message ??
          "Action mise en file offline (${_queueStats["total"]} en attente).",
    );
    if (_online) {
      await _syncNow(silent: true);
    }
  }

  Future<bool> _executeOrQueue({
    required String actionType,
    required String method,
    required String path,
    required Map<String, dynamic> payload,
    required Future<void> Function() runOnline,
    String? clientVersion,
    String? conflictPolicy,
    String? queuedMessage,
  }) async {
    if (!_online) {
      await _queueOfflineAction(
        actionType: actionType,
        method: method,
        path: path,
        payload: payload,
        clientVersion: clientVersion,
        conflictPolicy: conflictPolicy,
        message: queuedMessage,
      );
      return false;
    }
    try {
      await runOnline();
      return true;
    } catch (e) {
      if (_isNetworkError(e)) {
        await _queueOfflineAction(
          actionType: actionType,
          method: method,
          path: path,
          payload: payload,
          clientVersion: clientVersion,
          conflictPolicy: conflictPolicy,
          message:
              queuedMessage ??
              "Reseau indisponible, action mise en queue offline.",
        );
        return false;
      }
      rethrow;
    }
  }

  Future<void> _retryQueuedAction(Map<String, dynamic> action) async {
    final id = action["id"] as int?;
    if (id == null) return;
    await widget.localDb.resetQueuedActionFailure(id);
    await _reloadLocalState();
    await _syncNow();
  }

  Future<void> _deleteQueuedAction(Map<String, dynamic> action) async {
    final id = action["id"] as int?;
    if (id == null) return;
    await widget.localDb.deleteQueuedAction(id);
    await _reloadLocalState();
  }

  Future<void> _queueCreateShipment() async {
    final sender = _senderPhoneCtrl.text.trim();
    final receiverName = _receiverNameCtrl.text.trim();
    final receiverPhone = _receiverPhoneCtrl.text.trim();
    if (sender.isEmpty || receiverName.isEmpty || receiverPhone.isEmpty) return;

    final localId = "local_${DateTime.now().millisecondsSinceEpoch}";
    await widget.localDb.saveLocalShipmentDraft(
      localId: localId,
      senderPhone: sender,
      receiverName: receiverName,
      receiverPhone: receiverPhone,
    );
    await widget.localDb.queueAction(
      actionType: "create_shipment",
      method: "POST",
      path: "/shipments",
      payload: {
        "sender_phone": sender,
        "receiver_name": receiverName,
        "receiver_phone": receiverPhone,
        "origin": null,
        "destination": null,
      },
    );
    _receiverNameCtrl.clear();
    _receiverPhoneCtrl.clear();
    await _reloadLocalState();
    await _syncNow();
  }

  Future<void> _queuePickupValidate() async {
    final shipmentId = _pickupShipmentIdCtrl.text.trim();
    final code = _pickupCodeCtrl.text.trim();
    if (shipmentId.isEmpty || code.isEmpty) return;
    await widget.localDb.queueAction(
      actionType: "pickup_validate",
      method: "POST",
      path: "/codes/shipments/$shipmentId/pickup/validate",
      payload: {"code": code},
    );
    await _reloadLocalState();
    await _syncNow();
  }

  Future<void> _queuePickupConfirm() async {
    final shipmentId = _pickupShipmentIdCtrl.text.trim();
    final code = _pickupCodeCtrl.text.trim();
    final relayId = _pickupRelayIdCtrl.text.trim();
    if (shipmentId.isEmpty || code.isEmpty) return;
    final localShipment = await widget.localDb.getShipmentById(shipmentId);
    final clientVersion = localShipment?["updated_at"]?.toString();
    await widget.localDb.queueAction(
      actionType: "pickup_confirm",
      method: "POST",
      path: "/codes/shipments/$shipmentId/pickup/confirm",
      clientVersion: clientVersion,
      conflictPolicy: "server_wins",
      payload: {
        "code": code,
        "event_type": "shipment_delivered_to_receiver",
        "relay_id": relayId.isEmpty ? null : relayId,
      },
    );
    await _reloadLocalState();
    await _syncNow();
  }

  Future<void> _loadBackofficeOverview() async {
    try {
      final data = await widget.apiClient.backofficeOverview();
      if (!mounted) return;
      setState(() => _overview = data);
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur backoffice: $e");
    }
  }

  int _opsDelayedHours() {
    final parsed = int.tryParse(_opsDelayedHoursCtrl.text.trim());
    if (parsed == null) return 48;
    return parsed.clamp(1, 720);
  }

  double _opsRelayWarn() {
    final parsed = double.tryParse(_opsRelayWarnCtrl.text.trim());
    if (parsed == null) return 0.9;
    if (parsed < 0) return 0.0;
    if (parsed > 1) return 1.0;
    return parsed;
  }

  Future<void> _loadOpsMonitoringData() async {
    try {
      final delayedHours = _opsDelayedHours();
      final relayWarn = _opsRelayWarn();
      final alerts = await widget.apiClient.listBackofficeAlerts(
        delayedHours: delayedHours,
        relayUtilizationWarn: relayWarn,
        limit: 100,
      );
      final errors = await widget.apiClient.listRecentErrors(limit: 30);
      final worker = await widget.apiClient.getSmsWorkerStatus();
      if (!mounted) return;
      setState(() {
        _opsAlerts = alerts;
        _opsErrors = errors;
        _smsWorkerStatus = worker;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur dashboard ops: $e");
    }
  }

  Future<void> _runAutoDetectIncidents() async {
    try {
      final payload = {"delayed_hours": _opsDelayedHours(), "limit": 200};
      Map<String, dynamic> res = const {};
      final onlineExecuted = await _executeOrQueue(
        actionType: "backoffice_auto_detect_incidents",
        method: "POST",
        path:
            "/backoffice/incidents/auto-detect?delayed_hours=${_opsDelayedHours()}&limit=200",
        payload: payload,
        runOnline: () async {
          res = await widget.apiClient.autoDetectIncidents(
            delayedHours: _opsDelayedHours(),
            limit: 200,
          );
        },
        queuedMessage: "Auto-detect incidents mis en queue offline.",
      );
      if (!mounted) return;
      setState(() {
        if (onlineExecuted) {
          _lastAutoDetectResult = res;
        }
        _syncMessage = onlineExecuted
            ? "Auto-detect incidents execute"
            : "Auto-detect incidents mis en queue offline.";
      });
      if (onlineExecuted) {
        await _loadOpsMonitoringData();
        await _loadBackofficeOverview();
        await _loadIncidentClaimAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Auto-detect incidents impossible: $e");
    }
  }

  Future<void> _runNotifyCriticalAlerts() async {
    try {
      final payload = {
        "delayed_hours": _opsDelayedHours(),
        "relay_utilization_warn": _opsRelayWarn(),
      };
      Map<String, dynamic> res = const {};
      final onlineExecuted = await _executeOrQueue(
        actionType: "backoffice_notify_critical_alerts",
        method: "POST",
        path:
            "/backoffice/alerts/notify-critical?delayed_hours=${_opsDelayedHours()}&relay_utilization_warn=${_opsRelayWarn()}",
        payload: payload,
        runOnline: () async {
          res = await widget.apiClient.notifyCriticalAlerts(
            delayedHours: _opsDelayedHours(),
            relayUtilizationWarn: _opsRelayWarn(),
          );
        },
        queuedMessage: "Notification alertes critiques mise en queue offline.",
      );
      if (!mounted) return;
      setState(() {
        if (onlineExecuted) {
          _lastNotifyCriticalResult = res;
        }
        _syncMessage = onlineExecuted
            ? "Notification alertes critiques executee"
            : "Notification alertes critiques mise en queue offline.";
      });
      if (onlineExecuted) {
        await _loadOpsMonitoringData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Notification alertes impossible: $e");
    }
  }

  Future<void> _loadServerSyncConflictIncidents() async {
    try {
      final incidents = await widget.apiClient.listIncidents(
        incidentType: "sync_conflict",
        status: _syncConflictStatusFilter == "all"
            ? null
            : _syncConflictStatusFilter,
      );
      if (!mounted) return;
      setState(() {
        _serverSyncConflictIncidents = incidents;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur incidents sync_conflict: $e");
    }
  }

  Future<void> _resolveServerSyncConflictIncident(
    Map<String, dynamic> incident,
  ) async {
    final incidentId = incident["id"]?.toString();
    if (incidentId == null || incidentId.isEmpty) return;
    try {
      final payload = <String, dynamic>{"status": "resolved"};
      final onlineExecuted = await _executeOrQueue(
        actionType: "incident_resolve",
        method: "PATCH",
        path: "/incidents/$incidentId/status",
        payload: payload,
        runOnline: () async {
          await widget.apiClient.addIncidentUpdate(
            incidentId,
            "Resolved from mobile admin workflow.",
          );
          await widget.apiClient.updateIncidentStatus(incidentId, "resolved");
        },
        queuedMessage: "Resolution incident mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadServerSyncConflictIncidents();
        await _loadBackofficeOverview();
      }
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Incident sync_conflict resolu: $incidentId"
            : "Resolution incident mise en queue offline.",
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Resolution incident impossible: $e");
    }
  }

  Future<void> _showIncidentHistory(String incidentId) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: widget.apiClient.listIncidentUpdates(incidentId),
              builder: (context, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const SizedBox(
                    height: 180,
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snap.hasError) {
                  return Text("Erreur chargement historique: ${snap.error}");
                }
                final rows = snap.data ?? const [];
                if (rows.isEmpty) {
                  return const Text("Aucun historique pour cet incident.");
                }
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "Historique incident $incidentId",
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Flexible(
                      child: ListView.separated(
                        shrinkWrap: true,
                        itemCount: rows.length,
                        separatorBuilder: (_, __) => const Divider(height: 14),
                        itemBuilder: (context, index) {
                          final row = rows[index];
                          final msg = row["message"]?.toString() ?? "-";
                          final at = row["created_at"]?.toString() ?? "-";
                          return ListTile(
                            contentPadding: EdgeInsets.zero,
                            dense: true,
                            leading: const Icon(Icons.history_outlined),
                            title: Text(msg),
                            subtitle: Text(at),
                          );
                        },
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        );
      },
    );
  }

  Future<void> _loadPaymentAdminData() async {
    try {
      final statuses = await widget.apiClient.listPaymentStatuses();
      final payments = await widget.apiClient.listPayments(
        shipmentId: _paymentFilterShipmentCtrl.text.trim().isEmpty
            ? null
            : _paymentFilterShipmentCtrl.text.trim(),
        status: _paymentStatusFilter == "all" ? null : _paymentStatusFilter,
        payerPhone: _paymentFilterPayerCtrl.text.trim().isEmpty
            ? null
            : _paymentFilterPayerCtrl.text.trim(),
      );
      final commissions = await widget.apiClient.listCommissions();
      if (!mounted) return;
      setState(() {
        _paymentStatuses = statuses;
        _payments = payments;
        _commissions = commissions;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur chargement paiements: $e");
    }
  }

  Future<void> _createPaymentAdmin() async {
    final shipmentId = _paymentShipmentIdCtrl.text.trim();
    final amountRaw = _paymentAmountCtrl.text.trim();
    final amount = num.tryParse(amountRaw);
    final payerPhone = _paymentPayerPhoneCtrl.text.trim();
    final provider = _paymentProviderCtrl.text.trim();
    if (shipmentId.isEmpty ||
        amount == null ||
        amount <= 0 ||
        payerPhone.isEmpty ||
        provider.isEmpty) {
      return;
    }
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "payment_create",
        method: "POST",
        path: "/payments",
        payload: {
          "shipment_id": shipmentId,
          "amount": amount,
          "payer_phone": payerPhone,
          "payment_stage": _paymentStage,
          "provider": provider,
        },
        runOnline: () => widget.apiClient.createPayment(
          shipmentId: shipmentId,
          amount: amount,
          payerPhone: payerPhone,
          paymentStage: _paymentStage,
          provider: provider,
        ),
        queuedMessage: "Paiement mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Transaction de paiement creee"
            : "Paiement mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadPaymentAdminData();
        await _loadBackofficeOverview();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Creation paiement impossible: $e");
    }
  }

  Future<void> _runPaymentActionAdmin(String action) async {
    final paymentId = _paymentActionIdCtrl.text.trim();
    if (paymentId.isEmpty) return;
    try {
      String method = "POST";
      bool onlineExecuted = false;
      Map<String, dynamic> payload = const {};
      if (action == "initiate") {
        payload = {
          "external_ref": _paymentExternalRefCtrl.text.trim().isEmpty
              ? null
              : _paymentExternalRefCtrl.text.trim(),
        };
        onlineExecuted = await _executeOrQueue(
          actionType: "payment_initiate",
          method: method,
          path: "/payments/$paymentId/initiate",
          payload: payload,
          runOnline: () => widget.apiClient.initiatePayment(
            paymentId,
            externalRef: payload["external_ref"]?.toString(),
          ),
          queuedMessage: "Action paiement (initiate) mise en queue offline.",
        );
      } else if (action == "confirm") {
        payload = {
          "external_ref": _paymentExternalRefCtrl.text.trim().isEmpty
              ? null
              : _paymentExternalRefCtrl.text.trim(),
        };
        onlineExecuted = await _executeOrQueue(
          actionType: "payment_confirm",
          method: method,
          path: "/payments/$paymentId/confirm",
          payload: payload,
          runOnline: () => widget.apiClient.confirmPayment(
            paymentId,
            externalRef: payload["external_ref"]?.toString(),
          ),
          queuedMessage: "Action paiement (confirm) mise en queue offline.",
        );
      } else if (action == "fail") {
        payload = {
          "reason": _paymentFailReasonCtrl.text.trim().isEmpty
              ? "payment_provider_error"
              : _paymentFailReasonCtrl.text.trim(),
        };
        onlineExecuted = await _executeOrQueue(
          actionType: "payment_fail",
          method: method,
          path: "/payments/$paymentId/fail",
          payload: payload,
          runOnline: () => widget.apiClient.failPayment(
            paymentId,
            reason: payload["reason"]?.toString() ?? "payment_provider_error",
          ),
          queuedMessage: "Action paiement (fail) mise en queue offline.",
        );
      } else if (action == "cancel") {
        payload = {};
        onlineExecuted = await _executeOrQueue(
          actionType: "payment_cancel",
          method: method,
          path: "/payments/$paymentId/cancel",
          payload: payload,
          runOnline: () => widget.apiClient.cancelPayment(paymentId),
          queuedMessage: "Action paiement (cancel) mise en queue offline.",
        );
      } else if (action == "refund") {
        payload = {
          "reason": _paymentRefundReasonCtrl.text.trim().isEmpty
              ? "claim_refund"
              : _paymentRefundReasonCtrl.text.trim(),
        };
        onlineExecuted = await _executeOrQueue(
          actionType: "payment_refund",
          method: method,
          path: "/payments/$paymentId/refund",
          payload: payload,
          runOnline: () => widget.apiClient.refundPayment(
            paymentId,
            reason: payload["reason"]?.toString() ?? "claim_refund",
          ),
          queuedMessage: "Action paiement (refund) mise en queue offline.",
        );
      } else {
        return;
      }
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Action paiement executee: $action"
            : "Action paiement ($action) mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadPaymentAdminData();
        await _loadBackofficeOverview();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Action paiement impossible: $e");
    }
  }

  Future<void> _loadIncidentClaimAdminData() async {
    try {
      final incidents = await widget.apiClient.listIncidents(
        status: _incidentStatusFilter == "all" ? null : _incidentStatusFilter,
      );
      final claims = await widget.apiClient.listClaims(
        status: _claimStatusFilter == "all" ? null : _claimStatusFilter,
      );
      if (!mounted) return;
      setState(() {
        _adminIncidents = incidents;
        _adminClaims = claims;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur chargement incidents/claims: $e");
    }
  }

  Future<void> _createIncidentAdmin() async {
    final shipmentId = _incidentShipmentIdCtrl.text.trim();
    final description = _incidentDescriptionCtrl.text.trim();
    if (shipmentId.isEmpty || description.length < 4) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "incident_create",
        method: "POST",
        path: "/incidents",
        payload: {
          "shipment_id": shipmentId,
          "incident_type": _incidentTypeCreate,
          "description": description,
        },
        runOnline: () => widget.apiClient.createIncident(
          shipmentId: shipmentId,
          incidentType: _incidentTypeCreate,
          description: description,
        ),
        queuedMessage: "Incident mis en queue offline.",
      );
      _incidentDescriptionCtrl.clear();
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Incident cree"
            : "Incident mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadIncidentClaimAdminData();
        await _loadBackofficeOverview();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Creation incident impossible: $e");
    }
  }

  Future<void> _createClaimAdmin() async {
    final incidentId = _claimIncidentIdCtrl.text.trim();
    final shipmentId = _claimShipmentIdCtrl.text.trim();
    final amountRaw = _claimAmountCtrl.text.trim();
    final reason = _claimReasonCtrl.text.trim();
    final amount = num.tryParse(amountRaw);
    if (incidentId.isEmpty ||
        shipmentId.isEmpty ||
        amount == null ||
        amount <= 0 ||
        reason.length < 2) {
      return;
    }
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "claim_create",
        method: "POST",
        path: "/incidents/claims",
        payload: {
          "incident_id": incidentId,
          "shipment_id": shipmentId,
          "amount": amount,
          "reason": reason,
        },
        runOnline: () => widget.apiClient.createClaim(
          incidentId: incidentId,
          shipmentId: shipmentId,
          amount: amount,
          reason: reason,
        ),
        queuedMessage: "Claim mis en queue offline.",
      );
      _claimAmountCtrl.clear();
      _claimReasonCtrl.clear();
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Claim cree"
            : "Claim mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadIncidentClaimAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Creation claim impossible: $e");
    }
  }

  Future<void> _updateClaimStatusAdmin() async {
    final claimId = _claimIdUpdateCtrl.text.trim();
    if (claimId.isEmpty) return;
    try {
      final resolutionNote = _claimResolutionNoteCtrl.text.trim().isEmpty
          ? null
          : _claimResolutionNoteCtrl.text.trim();
      final onlineExecuted = await _executeOrQueue(
        actionType: "claim_status_update",
        method: "PATCH",
        path: "/incidents/claims/$claimId/status",
        payload: {
          "status": _claimStatusUpdate,
          "resolution_note": resolutionNote,
          "refunded_payment_id": null,
        },
        runOnline: () => widget.apiClient.updateClaimStatus(
          claimId: claimId,
          status: _claimStatusUpdate,
          resolutionNote: resolutionNote,
        ),
        queuedMessage: "Mise a jour claim mise en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Claim mis a jour"
            : "Mise a jour claim mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadIncidentClaimAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Maj claim impossible: $e");
    }
  }

  void _clearRelayForm() {
    _editingRelayId = "";
    _relayCodeCtrl.clear();
    _relayNameCtrl.clear();
    _relayTypeCtrl.text = "relay";
    _relayOpeningHoursCtrl.clear();
    _relayCapacityCtrl.clear();
    _relayIsActive = true;
  }

  void _prefillRelayForm(Map<String, dynamic> relay) {
    _editingRelayId = relay["id"]?.toString() ?? "";
    _relayCodeCtrl.text = relay["relay_code"]?.toString() ?? "";
    _relayNameCtrl.text = relay["name"]?.toString() ?? "";
    _relayTypeCtrl.text = relay["type"]?.toString() ?? "relay";
    _relayOpeningHoursCtrl.text = relay["opening_hours"]?.toString() ?? "";
    _relayCapacityCtrl.text = relay["storage_capacity"]?.toString() ?? "";
    _relayIsActive = relay["is_active"] == true;
  }

  Future<void> _loadRelayAdminData() async {
    try {
      final relays = await widget.apiClient.listRelays();
      final agents = await widget.apiClient.listUsers(role: "agent");
      if (!mounted) return;
      setState(() {
        _relays = relays;
        _agents = agents;
        if (_selectedRelayId.isEmpty && _relays.isNotEmpty) {
          _selectedRelayId = _relays.first["id"]?.toString() ?? "";
        }
        if (_selectedRelayId.isNotEmpty &&
            !_relays.any((r) => r["id"]?.toString() == _selectedRelayId)) {
          _selectedRelayId = _relays.isEmpty
              ? ""
              : (_relays.first["id"]?.toString() ?? "");
        }
      });
      await _loadSelectedRelayDetails();
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur chargement relais/agents: $e");
    }
  }

  Future<void> _loadSelectedRelayDetails() async {
    if (_selectedRelayId.isEmpty) {
      if (!mounted) return;
      setState(() {
        _relayAgents = const [];
        _relayCapacity = null;
      });
      return;
    }
    try {
      final relayAgents = await widget.apiClient.listRelayAgents(
        _selectedRelayId,
      );
      final relayCapacity = await widget.apiClient.getRelayCapacity(
        _selectedRelayId,
      );
      if (!mounted) return;
      setState(() {
        _relayAgents = relayAgents;
        _relayCapacity = relayCapacity;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur details relais: $e");
    }
  }

  Future<void> _submitRelayForm() async {
    final code = _relayCodeCtrl.text.trim();
    final name = _relayNameCtrl.text.trim();
    final type = _relayTypeCtrl.text.trim();
    if (code.isEmpty || name.isEmpty || type.isEmpty) return;
    final capacityRaw = _relayCapacityCtrl.text.trim();
    final parsedCapacity = capacityRaw.isEmpty
        ? null
        : int.tryParse(capacityRaw);
    if (capacityRaw.isNotEmpty && parsedCapacity == null) {
      setState(() => _syncMessage = "Capacite invalide");
      return;
    }
    final payload = <String, dynamic>{
      "relay_code": code,
      "name": name,
      "type": type,
      "opening_hours": _relayOpeningHoursCtrl.text.trim().isEmpty
          ? null
          : _relayOpeningHoursCtrl.text.trim(),
      "storage_capacity": parsedCapacity,
      "is_active": _relayIsActive,
    };
    try {
      if (_editingRelayId.isEmpty) {
        final onlineExecuted = await _executeOrQueue(
          actionType: "relay_create",
          method: "POST",
          path: "/relays",
          payload: payload,
          runOnline: () => widget.apiClient.createRelay(payload),
          queuedMessage: "Creation relais mise en queue offline.",
        );
        if (!mounted) return;
        setState(
          () => _syncMessage = onlineExecuted
              ? "Relais cree"
              : "Creation relais mise en queue offline.",
        );
        if (onlineExecuted) {
          await _loadRelayAdminData();
        }
      } else {
        final onlineExecuted = await _executeOrQueue(
          actionType: "relay_update",
          method: "PATCH",
          path: "/relays/$_editingRelayId",
          payload: payload,
          runOnline: () =>
              widget.apiClient.updateRelay(_editingRelayId, payload),
          queuedMessage: "Mise a jour relais mise en queue offline.",
        );
        if (!mounted) return;
        setState(
          () => _syncMessage = onlineExecuted
              ? "Relais mis a jour"
              : "Mise a jour relais mise en queue offline.",
        );
        if (onlineExecuted) {
          await _loadRelayAdminData();
        }
      }
      if (!mounted) return;
      setState(_clearRelayForm);
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur sauvegarde relais: $e");
    }
  }

  Future<void> _deleteSelectedRelay() async {
    if (_selectedRelayId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "relay_delete",
        method: "DELETE",
        path: "/relays/$_selectedRelayId",
        payload: const {},
        runOnline: () => widget.apiClient.deleteRelay(_selectedRelayId),
        queuedMessage: "Suppression relais mise en queue offline.",
      );
      if (!mounted) return;
      setState(() {
        _syncMessage = onlineExecuted
            ? "Relais supprime"
            : "Suppression relais mise en queue offline.";
        if (_editingRelayId == _selectedRelayId) {
          _clearRelayForm();
        }
      });
      if (onlineExecuted) {
        await _loadRelayAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Suppression relais impossible: $e");
    }
  }

  Future<void> _assignAgentToSelectedRelay() async {
    if (_selectedRelayId.isEmpty || _assignAgentId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "relay_assign_agent",
        method: "PUT",
        path: "/relays/$_selectedRelayId/agents/$_assignAgentId",
        payload: const {},
        runOnline: () => widget.apiClient.assignAgentToRelay(
          _selectedRelayId,
          _assignAgentId,
        ),
        queuedMessage: "Affectation agent mise en queue offline.",
      );
      if (!mounted) return;
      setState(() {
        _syncMessage = onlineExecuted
            ? "Agent rattache au relais"
            : "Affectation agent mise en queue offline.";
        _assignAgentId = "";
      });
      if (onlineExecuted) {
        await _loadRelayAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Affectation agent impossible: $e");
    }
  }

  Future<void> _unassignAgentFromSelectedRelay(String userId) async {
    if (_selectedRelayId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "relay_unassign_agent",
        method: "DELETE",
        path: "/relays/$_selectedRelayId/agents/$userId",
        payload: const {},
        runOnline: () =>
            widget.apiClient.unassignAgentFromRelay(_selectedRelayId, userId),
        queuedMessage: "Detachement agent mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Agent detache du relais"
            : "Detachement agent mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadRelayAdminData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Detachement agent impossible: $e");
    }
  }

  Future<void> _loadTransportData() async {
    try {
      final trips = await widget.apiClient.listTrips();
      if (!mounted) return;
      setState(() {
        _trips = trips;
        if (_selectedTripId.isEmpty && _trips.isNotEmpty) {
          _selectedTripId = _trips.first["id"]?.toString() ?? "";
        }
        if (_selectedTripId.isNotEmpty &&
            !_trips.any((t) => t["id"]?.toString() == _selectedTripId)) {
          _selectedTripId = _trips.isEmpty
              ? ""
              : (_trips.first["id"]?.toString() ?? "");
        }
      });
      await _loadSelectedTripManifest();
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur chargement trips: $e");
    }
  }

  Future<void> _loadSelectedTripManifest() async {
    if (_selectedTripId.isEmpty) {
      if (!mounted) return;
      setState(() {
        _tripManifestShipments = const [];
      });
      return;
    }
    try {
      final data = await widget.apiClient.getTripManifest(_selectedTripId);
      if (!mounted) return;
      final trip = Map<String, dynamic>.from(
        data["trip"] as Map<String, dynamic>? ?? const {},
      );
      final shipments = (data["shipments"] as List<dynamic>? ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      setState(() {
        _tripManifestShipments = shipments;
        _tripStatusCtrl.text = trip["status"]?.toString() ?? "planned";
        _tripRouteIdCtrl.text = trip["route_id"]?.toString() ?? "";
        _tripVehicleIdCtrl.text = trip["vehicle_id"]?.toString() ?? "";
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Erreur chargement manifest: $e");
    }
  }

  Future<void> _createTrip() async {
    final status = _tripStatusCtrl.text.trim();
    if (status.isEmpty) return;
    try {
      final payload = <String, dynamic>{
        "route_id": _tripRouteIdCtrl.text.trim().isEmpty
            ? null
            : _tripRouteIdCtrl.text.trim(),
        "vehicle_id": _tripVehicleIdCtrl.text.trim().isEmpty
            ? null
            : _tripVehicleIdCtrl.text.trim(),
        "status": status,
      };
      final onlineExecuted = await _executeOrQueue(
        actionType: "trip_create",
        method: "POST",
        path: "/transport/trips",
        payload: payload,
        runOnline: () => widget.apiClient.createTrip(payload),
        queuedMessage: "Creation trip mise en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Trip cree"
            : "Creation trip mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadTransportData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Creation trip impossible: $e");
    }
  }

  Future<void> _updateSelectedTrip() async {
    if (_selectedTripId.isEmpty) return;
    final status = _tripStatusCtrl.text.trim();
    if (status.isEmpty) return;
    try {
      final payload = <String, dynamic>{
        "route_id": _tripRouteIdCtrl.text.trim().isEmpty
            ? null
            : _tripRouteIdCtrl.text.trim(),
        "vehicle_id": _tripVehicleIdCtrl.text.trim().isEmpty
            ? null
            : _tripVehicleIdCtrl.text.trim(),
        "status": status,
      };
      final onlineExecuted = await _executeOrQueue(
        actionType: "trip_update",
        method: "PATCH",
        path: "/transport/trips/$_selectedTripId",
        payload: payload,
        runOnline: () => widget.apiClient.updateTrip(_selectedTripId, payload),
        queuedMessage: "Mise a jour trip mise en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Trip mis a jour"
            : "Mise a jour trip mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadTransportData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Mise a jour trip impossible: $e");
    }
  }

  Future<void> _completeSelectedTrip() async {
    if (_selectedTripId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "trip_complete",
        method: "POST",
        path: "/transport/trips/$_selectedTripId/complete",
        payload: const {},
        runOnline: () => widget.apiClient.completeTrip(_selectedTripId),
        queuedMessage: "Completion trip mise en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Trip complete"
            : "Completion trip mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadTransportData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Completion trip impossible: $e");
    }
  }

  Future<void> _addShipmentToSelectedManifest() async {
    if (_selectedTripId.isEmpty) return;
    final shipmentId = _manifestShipmentIdCtrl.text.trim();
    if (shipmentId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "manifest_add_shipment",
        method: "POST",
        path: "/transport/trips/$_selectedTripId/manifest/shipments",
        payload: {"shipment_id": shipmentId},
        runOnline: () =>
            widget.apiClient.addShipmentToManifest(_selectedTripId, shipmentId),
        queuedMessage: "Ajout manifest mis en queue offline.",
      );
      _manifestShipmentIdCtrl.clear();
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Shipment ajoute au manifest"
            : "Ajout manifest mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadSelectedTripManifest();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Ajout manifest impossible: $e");
    }
  }

  Future<void> _removeShipmentFromSelectedManifest(String shipmentId) async {
    if (_selectedTripId.isEmpty || shipmentId.isEmpty) return;
    try {
      final onlineExecuted = await _executeOrQueue(
        actionType: "manifest_remove_shipment",
        method: "DELETE",
        path:
            "/transport/trips/$_selectedTripId/manifest/shipments/$shipmentId",
        payload: const {},
        runOnline: () => widget.apiClient.removeShipmentFromManifest(
          _selectedTripId,
          shipmentId,
        ),
        queuedMessage: "Retrait manifest mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Shipment retire du manifest"
            : "Retrait manifest mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadSelectedTripManifest();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Retrait manifest impossible: $e");
    }
  }

  Future<void> _autoAssignPriorityToSelectedManifest() async {
    if (_selectedTripId.isEmpty) return;
    final vehicleCapacity = int.tryParse(_tripVehicleCapacityCtrl.text.trim());
    try {
      final payload = <String, dynamic>{
        "target_manifest_size": 20,
        "max_add": 10,
        "candidate_limit": 500,
        "vehicle_capacity": vehicleCapacity,
      };
      Map<String, dynamic> res = const {};
      final onlineExecuted = await _executeOrQueue(
        actionType: "manifest_auto_assign_priority",
        method: "POST",
        path: "/transport/trips/$_selectedTripId/manifest/auto-assign-priority",
        payload: payload,
        runOnline: () async {
          res = await widget.apiClient.autoAssignPriorityToManifest(
            _selectedTripId,
            vehicleCapacity: vehicleCapacity,
          );
        },
        queuedMessage: "Auto-assign mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Auto-assign OK: +${res["added_count"]} / rejetes ${res["rejected_count"]}"
            : "Auto-assign mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadSelectedTripManifest();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Auto-assign impossible: $e");
    }
  }

  Future<void> _scanSelectedTripDeparture() async {
    if (_selectedTripId.isEmpty) return;
    final relayId = _tripScanRelayIdCtrl.text.trim();
    try {
      final payload = <String, dynamic>{
        "relay_id": relayId.isEmpty ? null : relayId,
        "event_type": null,
      };
      Map<String, dynamic> res = const {};
      final onlineExecuted = await _executeOrQueue(
        actionType: "trip_scan_departure",
        method: "POST",
        path: "/transport/trips/$_selectedTripId/scan/departure",
        payload: payload,
        runOnline: () async {
          res = await widget.apiClient.scanTripDeparture(
            _selectedTripId,
            relayId: relayId.isEmpty ? null : relayId,
          );
        },
        queuedMessage: "Scan depart mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Scan depart OK: ${res["updated_shipments"]} colis mis a jour"
            : "Scan depart mis en queue offline.",
      );
      if (onlineExecuted) {
        await _loadTransportData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Scan depart impossible: $e");
    }
  }

  Future<void> _scanSelectedTripArrival() async {
    if (_selectedTripId.isEmpty) return;
    final relayId = _tripScanRelayIdCtrl.text.trim();
    try {
      final payload = <String, dynamic>{
        "relay_id": relayId.isEmpty ? null : relayId,
        "event_type": null,
      };
      Map<String, dynamic> res = const {};
      final onlineExecuted = await _executeOrQueue(
        actionType: "trip_scan_arrival",
        method: "POST",
        path: "/transport/trips/$_selectedTripId/scan/arrival",
        payload: payload,
        runOnline: () async {
          res = await widget.apiClient.scanTripArrival(
            _selectedTripId,
            relayId: relayId.isEmpty ? null : relayId,
          );
        },
        queuedMessage: "Scan arrivee mis en queue offline.",
      );
      if (!mounted) return;
      setState(
        () => _syncMessage = onlineExecuted
            ? "Scan arrivee OK: ${res["updated_shipments"]} colis mis a jour"
            : "Scan arrivee mise en queue offline.",
      );
      if (onlineExecuted) {
        await _loadTransportData();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _syncMessage = "Scan arrivee impossible: $e");
    }
  }

  Future<void> _retryConflictClientWins(Map<String, dynamic> conflict) async {
    final payload = widget.localDb.decodeActionPayload(conflict);
    await widget.localDb.queueAction(
      actionType: conflict["action_type"]?.toString() ?? "unknown",
      method: conflict["method"]?.toString() ?? "POST",
      path: conflict["path"]?.toString() ?? "/",
      payload: payload,
      conflictPolicy: "client_wins",
      clientVersion: null,
    );
    final conflictId = conflict["client_action_id"]?.toString();
    if (conflictId != null && conflictId.isNotEmpty) {
      await widget.localDb.deleteSyncConflict(conflictId);
    }
    await _reloadLocalState();
    await _syncNow();
  }

  Widget _statusChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        color: color.withValues(alpha: 0.1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionCard({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: AppTheme.brandSecondary),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }

  Widget _buildOfflineQueueCard() {
    return _sectionCard(
      title: "Offline Queue",
      icon: Icons.cloud_off_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            "Actions en attente: ${_queueStats["total"]} | echecs: ${_queueStats["failed"]}",
          ),
          const SizedBox(height: 8),
          if (_queuedActions.isEmpty)
            const Text("Aucune action en queue.")
          else
            ..._queuedActions.take(12).map((action) {
              final attempts = action["attempts"] as int? ?? 0;
              final status = attempts > 0 ? "failed" : "pending";
              final actionType = action["action_type"]?.toString() ?? "unknown";
              final path = action["path"]?.toString() ?? "/";
              final lastError = action["last_error"]?.toString() ?? "";
              return ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                leading: Icon(
                  status == "failed"
                      ? Icons.error_outline
                      : Icons.schedule_outlined,
                ),
                title: Text("$actionType [$status]"),
                subtitle: Text(
                  lastError.isEmpty
                      ? "$path | attempts: $attempts"
                      : "$path | attempts: $attempts\n$lastError",
                ),
                trailing: Wrap(
                  spacing: 6,
                  children: [
                    OutlinedButton(
                      onPressed: () => _retryQueuedAction(action),
                      child: const Text("Retry"),
                    ),
                    OutlinedButton(
                      onPressed: () => _deleteQueuedAction(action),
                      child: const Text("Suppr."),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _buildCustomerTab() {
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        _sectionCard(
          title: "Creation Colis",
          icon: Icons.inventory_2_outlined,
          child: Column(
            children: [
              TextField(
                controller: _senderPhoneCtrl,
                decoration: const InputDecoration(
                  labelText: "Sender phone",
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _receiverNameCtrl,
                decoration: const InputDecoration(
                  labelText: "Receiver name",
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _receiverPhoneCtrl,
                decoration: const InputDecoration(
                  labelText: "Receiver phone",
                  prefixIcon: Icon(Icons.call_outlined),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _queueCreateShipment,
                  icon: const Icon(Icons.add_task),
                  label: const Text("Creer colis (offline queue)"),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Colis Locaux",
          icon: Icons.list_alt_outlined,
          child: Column(
            children: _shipments.take(20).map((s) {
              return ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                leading: const Icon(Icons.local_shipping_outlined),
                title: Text(s["shipment_no"]?.toString() ?? s["id"].toString()),
                subtitle: Text(
                  "status: ${s["status"] ?? "-"} | receiver: ${s["receiver_name"] ?? "-"}",
                ),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 10),
        _buildOfflineQueueCard(),
      ],
    );
  }

  Widget _buildAgentTab() {
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        _sectionCard(
          title: "Validation Retrait",
          icon: Icons.qr_code_scanner_outlined,
          child: Column(
            children: [
              TextField(
                controller: _pickupShipmentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Shipment ID",
                  prefixIcon: Icon(Icons.confirmation_number_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _pickupCodeCtrl,
                decoration: const InputDecoration(
                  labelText: "Pickup code",
                  prefixIcon: Icon(Icons.pin_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _pickupRelayIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Relay ID (optionnel)",
                  prefixIcon: Icon(Icons.store_mall_directory_outlined),
                ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _queuePickupValidate,
                    icon: const Icon(Icons.rule),
                    label: const Text("Queue validate"),
                  ),
                  FilledButton.icon(
                    onPressed: _queuePickupConfirm,
                    icon: const Icon(Icons.verified),
                    label: const Text("Queue confirm"),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Sync Conflicts",
          icon: Icons.warning_amber_rounded,
          child: Column(
            children: [
              if (_syncConflicts.isEmpty) const Text("Aucun conflit de sync."),
              ..._syncConflicts.take(8).map((conflict) {
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  leading: const Icon(Icons.report_gmailerrorred_outlined),
                  title: Text(
                    conflict["action_type"]?.toString() ?? "unknown_action",
                  ),
                  subtitle: Text(
                    conflict["reason"]?.toString() ?? "Conflit detecte",
                  ),
                  trailing: FilledButton(
                    onPressed: () => _retryConflictClientWins(conflict),
                    child: const Text("Retry client_wins"),
                  ),
                );
              }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _buildOfflineQueueCard(),
      ],
    );
  }

  Widget _buildAdminTab() {
    final shipmentQuery = _syncIncidentShipmentFilterCtrl.text
        .trim()
        .toLowerCase();
    final filteredSyncIncidents = _serverSyncConflictIncidents.where((
      incident,
    ) {
      if (shipmentQuery.isEmpty) return true;
      final shipmentId =
          incident["shipment_id"]?.toString().toLowerCase() ?? "";
      return shipmentId.contains(shipmentQuery);
    }).toList();
    Map<String, dynamic>? selectedRelay;
    for (final relay in _relays) {
      if (relay["id"]?.toString() == _selectedRelayId) {
        selectedRelay = relay;
        break;
      }
    }
    final unassignedAgents = _agents
        .where((agent) => agent["relay_id"] == null)
        .toList();
    Map<String, dynamic>? selectedTrip;
    for (final trip in _trips) {
      if (trip["id"]?.toString() == _selectedTripId) {
        selectedTrip = trip;
        break;
      }
    }
    final incidentTypes = const ["lost", "damaged", "delayed", "claim"];
    final claimStatuses = const [
      "submitted",
      "reviewing",
      "approved",
      "rejected",
      "paid",
    ];
    final paymentStages = const ["at_send", "at_delivery"];
    final paymentStatusesForFilter = [
      "all",
      ..._paymentStatuses.where((status) => status.isNotEmpty),
    ];

    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        _sectionCard(
          title: "Ops Dashboard",
          icon: Icons.monitor_heart_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: () async {
                      await _loadBackofficeOverview();
                      await _loadOpsMonitoringData();
                    },
                    icon: const Icon(Icons.sync_outlined),
                    label: const Text("Refresh dashboard"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _runAutoDetectIncidents,
                    icon: const Icon(Icons.auto_awesome_outlined),
                    label: const Text("Auto-detect incidents"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _runNotifyCriticalAlerts,
                    icon: const Icon(Icons.sms_outlined),
                    label: const Text("Notify critical SMS"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _opsDelayedHoursCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: "Delayed hours",
                        prefixIcon: Icon(Icons.hourglass_bottom_outlined),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _opsRelayWarnCtrl,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: const InputDecoration(
                        labelText: "Relay warn (0-1)",
                        prefixIcon: Icon(Icons.storage_outlined),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              if (_overview != null) ...[
                Text(
                  "Shipments total: ${_overview!["shipments_total"]} | today: ${_overview!["shipments_today"]}",
                ),
                Text(
                  "Payments total: ${_overview!["payments_total"]} | failed24h: ${_overview!["payments_failed_24h"]}",
                ),
                Text(
                  "Incidents open: ${_overview!["incidents_open"]} | Trips in progress: ${_overview!["trips_in_progress"]}",
                ),
                Text(
                  "Notif pending: ${_overview!["notifications_pending"]} | dead: ${_overview!["notifications_dead"]}",
                ),
                Text(
                  "Auto-assign acceptance 24h: ${_overview!["auto_assign_acceptance_rate_24h"]}%",
                ),
              ],
              if (_smsWorkerStatus != null) ...[
                const SizedBox(height: 8),
                Text(
                  "SMS worker: running=${_smsWorkerStatus!["running"]} | enabled=${_smsWorkerStatus!["enabled"]} | leader=${_smsWorkerStatus!["leader_acquired"]}",
                ),
              ],
              if (_lastAutoDetectResult != null) ...[
                const SizedBox(height: 8),
                Text(
                  "Auto-detect: examined ${_lastAutoDetectResult!["examined"]}, created ${_lastAutoDetectResult!["created"]}, skipped ${_lastAutoDetectResult!["skipped_existing"]}",
                ),
              ],
              if (_lastNotifyCriticalResult != null) ...[
                const SizedBox(height: 8),
                Text(
                  "Notify critical: alerts ${_lastNotifyCriticalResult!["critical_count"]}, recipients ${_lastNotifyCriticalResult!["recipients_count"]}, sent ${_lastNotifyCriticalResult!["sent_count"]}",
                ),
              ],
              const Divider(height: 20),
              Text(
                "Operational alerts (${_opsAlerts.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_opsAlerts.isEmpty)
                const Text("Aucune alerte operationnelle.")
              else
                ..._opsAlerts.take(8).map((alert) {
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: const Icon(Icons.notification_important_outlined),
                    title: Text(
                      "${alert["severity"] ?? "-"} | ${alert["title"] ?? "-"}",
                    ),
                    subtitle: Text(alert["details"]?.toString() ?? "-"),
                  );
                }),
              const SizedBox(height: 8),
              Text(
                "Recent errors (${_opsErrors.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_opsErrors.isEmpty)
                const Text("Aucune erreur recente.")
              else
                ..._opsErrors.take(6).map((row) {
                  final source = row["source"]?.toString() ?? "-";
                  final record = row["record"]?.toString() ?? "-";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: const Icon(Icons.bug_report_outlined),
                    title: Text(source),
                    subtitle: Text(record),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Paiements & Commissions",
          icon: Icons.account_balance_wallet_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _loadPaymentAdminData,
                    icon: const Icon(Icons.sync_outlined),
                    label: const Text("Charger paiements"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _paymentStatusFilter,
                items: paymentStatusesForFilter
                    .map(
                      (status) => DropdownMenuItem<String>(
                        value: status,
                        child: Text("Status: $status"),
                      ),
                    )
                    .toList(),
                onChanged: (value) async {
                  if (value == null) return;
                  setState(() => _paymentStatusFilter = value);
                  await _loadPaymentAdminData();
                },
                decoration: const InputDecoration(
                  labelText: "Filtre status paiement",
                  prefixIcon: Icon(Icons.filter_alt_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentFilterShipmentCtrl,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: "Filtre shipment_id",
                  prefixIcon: Icon(Icons.inventory_2_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentFilterPayerCtrl,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: "Filtre payer phone",
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _loadPaymentAdminData,
                icon: const Icon(Icons.search_outlined),
                label: const Text("Appliquer filtres"),
              ),
              const Divider(height: 20),
              Text(
                "Creer transaction",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentShipmentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Shipment ID",
                  prefixIcon: Icon(Icons.local_shipping_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentAmountCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: "Montant",
                  prefixIcon: Icon(Icons.payments_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentPayerPhoneCtrl,
                decoration: const InputDecoration(
                  labelText: "Telephone payeur",
                  prefixIcon: Icon(Icons.phone_iphone_outlined),
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _paymentStage,
                items: paymentStages
                    .map(
                      (stage) => DropdownMenuItem<String>(
                        value: stage,
                        child: Text("Stage: $stage"),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _paymentStage = value);
                  }
                },
                decoration: const InputDecoration(
                  labelText: "Etape paiement",
                  prefixIcon: Icon(Icons.timeline_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentProviderCtrl,
                decoration: const InputDecoration(
                  labelText: "Provider",
                  prefixIcon: Icon(Icons.account_tree_outlined),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _createPaymentAdmin,
                icon: const Icon(Icons.add_card_outlined),
                label: const Text("Creer paiement"),
              ),
              const Divider(height: 20),
              Text(
                "Actions transaction",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentActionIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Payment ID",
                  prefixIcon: Icon(Icons.numbers_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentExternalRefCtrl,
                decoration: const InputDecoration(
                  labelText: "External ref (optionnel)",
                  prefixIcon: Icon(Icons.link_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentFailReasonCtrl,
                decoration: const InputDecoration(
                  labelText: "Raison echec",
                  prefixIcon: Icon(Icons.error_outline),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _paymentRefundReasonCtrl,
                decoration: const InputDecoration(
                  labelText: "Raison remboursement",
                  prefixIcon: Icon(Icons.replay_outlined),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton(
                    onPressed: () => _runPaymentActionAdmin("initiate"),
                    child: const Text("Initier"),
                  ),
                  FilledButton(
                    onPressed: () => _runPaymentActionAdmin("confirm"),
                    child: const Text("Confirmer"),
                  ),
                  OutlinedButton(
                    onPressed: () => _runPaymentActionAdmin("fail"),
                    child: const Text("Marquer echec"),
                  ),
                  OutlinedButton(
                    onPressed: () => _runPaymentActionAdmin("cancel"),
                    child: const Text("Annuler"),
                  ),
                  OutlinedButton(
                    onPressed: () => _runPaymentActionAdmin("refund"),
                    child: const Text("Rembourser"),
                  ),
                ],
              ),
              const Divider(height: 20),
              Text(
                "Transactions (${_payments.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_payments.isEmpty)
                const Text("Aucune transaction.")
              else
                ..._payments.take(10).map((payment) {
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.account_balance_wallet_outlined),
                    title: Text(payment["id"]?.toString() ?? "-"),
                    subtitle: Text(
                      "shipment: ${payment["shipment_id"] ?? "-"} | amount: ${payment["amount"] ?? "-"} | status: ${payment["status"] ?? "-"}\n"
                      "stage: ${payment["payment_stage"] ?? "-"} | provider: ${payment["provider"] ?? "-"} | payer: ${payment["payer_phone"] ?? "-"}",
                    ),
                  );
                }),
              const SizedBox(height: 8),
              Text(
                "Commissions (${_commissions.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_commissions.isEmpty)
                const Text("Aucune commission.")
              else
                ..._commissions.take(10).map((row) {
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: const Icon(Icons.receipt_long_outlined),
                    title: Text(
                      "${row["commission_type"] ?? "-"} | ${row["amount"] ?? "-"}",
                    ),
                    subtitle: Text(
                      "payment: ${row["payment_id"] ?? "-"} | beneficiary: ${row["beneficiary_kind"] ?? "-"}:${row["beneficiary_id"] ?? "-"} | status: ${row["status"] ?? "-"}",
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Incidents & Claims",
          icon: Icons.health_and_safety_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _loadIncidentClaimAdminData,
                    icon: const Icon(Icons.sync_outlined),
                    label: const Text("Charger incidents/claims"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _incidentStatusFilter,
                items: const [
                  DropdownMenuItem(value: "all", child: Text("Incidents: all")),
                  DropdownMenuItem(
                    value: "open",
                    child: Text("Incidents: open"),
                  ),
                  DropdownMenuItem(
                    value: "investigating",
                    child: Text("Incidents: investigating"),
                  ),
                  DropdownMenuItem(
                    value: "resolved",
                    child: Text("Incidents: resolved"),
                  ),
                ],
                onChanged: (value) async {
                  if (value == null) return;
                  setState(() => _incidentStatusFilter = value);
                  await _loadIncidentClaimAdminData();
                },
                decoration: const InputDecoration(
                  labelText: "Filtre statut incidents",
                  prefixIcon: Icon(Icons.filter_list_outlined),
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _claimStatusFilter,
                items: const [
                  DropdownMenuItem(value: "all", child: Text("Claims: all")),
                  DropdownMenuItem(
                    value: "submitted",
                    child: Text("Claims: submitted"),
                  ),
                  DropdownMenuItem(
                    value: "reviewing",
                    child: Text("Claims: reviewing"),
                  ),
                  DropdownMenuItem(
                    value: "approved",
                    child: Text("Claims: approved"),
                  ),
                  DropdownMenuItem(
                    value: "rejected",
                    child: Text("Claims: rejected"),
                  ),
                  DropdownMenuItem(value: "paid", child: Text("Claims: paid")),
                ],
                onChanged: (value) async {
                  if (value == null) return;
                  setState(() => _claimStatusFilter = value);
                  await _loadIncidentClaimAdminData();
                },
                decoration: const InputDecoration(
                  labelText: "Filtre statut claims",
                  prefixIcon: Icon(Icons.filter_alt_outlined),
                ),
              ),
              const Divider(height: 20),
              Text(
                "Creer incident",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _incidentShipmentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Shipment ID",
                  prefixIcon: Icon(Icons.inventory_2_outlined),
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _incidentTypeCreate,
                items: incidentTypes
                    .map(
                      (v) => DropdownMenuItem<String>(
                        value: v,
                        child: Text("Type: $v"),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _incidentTypeCreate = value);
                  }
                },
                decoration: const InputDecoration(
                  labelText: "Type incident",
                  prefixIcon: Icon(Icons.report_problem_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _incidentDescriptionCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: "Description",
                  prefixIcon: Icon(Icons.description_outlined),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _createIncidentAdmin,
                icon: const Icon(Icons.add_alert_outlined),
                label: const Text("Creer incident"),
              ),
              const Divider(height: 20),
              Text(
                "Creer claim",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimIncidentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Incident ID",
                  prefixIcon: Icon(Icons.report_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimShipmentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Shipment ID",
                  prefixIcon: Icon(Icons.local_shipping_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimAmountCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: "Amount",
                  prefixIcon: Icon(Icons.payments_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimReasonCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: "Reason",
                  prefixIcon: Icon(Icons.notes_outlined),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _createClaimAdmin,
                icon: const Icon(Icons.receipt_long_outlined),
                label: const Text("Creer claim"),
              ),
              const Divider(height: 20),
              Text(
                "Mettre a jour claim",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimIdUpdateCtrl,
                decoration: const InputDecoration(
                  labelText: "Claim ID",
                  prefixIcon: Icon(Icons.numbers_outlined),
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _claimStatusUpdate,
                items: claimStatuses
                    .map(
                      (v) => DropdownMenuItem<String>(
                        value: v,
                        child: Text("Status: $v"),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _claimStatusUpdate = value);
                  }
                },
                decoration: const InputDecoration(
                  labelText: "Nouveau statut",
                  prefixIcon: Icon(Icons.task_alt_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _claimResolutionNoteCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: "Resolution note (optionnel)",
                  prefixIcon: Icon(Icons.edit_note_outlined),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _updateClaimStatusAdmin,
                icon: const Icon(Icons.update_outlined),
                label: const Text("Maj statut claim"),
              ),
              const Divider(height: 20),
              Text(
                "Incidents (${_adminIncidents.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_adminIncidents.isEmpty)
                const Text("Aucun incident.")
              else
                ..._adminIncidents.take(10).map((incident) {
                  final id = incident["id"]?.toString() ?? "-";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    onTap: () => _showIncidentHistory(id),
                    leading: const Icon(Icons.warning_amber_outlined),
                    title: Text("Incident $id"),
                    subtitle: Text(
                      "shipment: ${incident["shipment_id"] ?? "-"} | status: ${incident["status"] ?? "-"}",
                    ),
                  );
                }),
              const SizedBox(height: 8),
              Text(
                "Claims (${_adminClaims.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              if (_adminClaims.isEmpty)
                const Text("Aucun claim.")
              else
                ..._adminClaims.take(10).map((claim) {
                  final id = claim["id"]?.toString() ?? "-";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.request_quote_outlined),
                    title: Text("Claim $id"),
                    subtitle: Text(
                      "shipment: ${claim["shipment_id"] ?? "-"} | status: ${claim["status"] ?? "-"} | amount: ${claim["amount"] ?? "-"}",
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Transport Ops",
          icon: Icons.alt_route_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _loadTransportData,
                    icon: const Icon(Icons.sync_outlined),
                    label: const Text("Charger trips"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _createTrip,
                    icon: const Icon(Icons.add_road_outlined),
                    label: const Text("Creer trip"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _updateSelectedTrip,
                    icon: const Icon(Icons.edit_road_outlined),
                    label: const Text("Maj trip"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _completeSelectedTrip,
                    icon: const Icon(Icons.check_circle_outline),
                    label: const Text("Completer"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _selectedTripId.isEmpty ? null : _selectedTripId,
                items: _trips
                    .map(
                      (trip) => DropdownMenuItem<String>(
                        value: trip["id"]?.toString() ?? "",
                        child: Text(
                          "${trip["id"]?.toString().substring(0, 8) ?? "-"} | ${trip["status"] ?? "-"}",
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) async {
                  setState(() => _selectedTripId = value ?? "");
                  await _loadSelectedTripManifest();
                },
                decoration: const InputDecoration(
                  labelText: "Trip selectionne",
                  prefixIcon: Icon(Icons.route_outlined),
                ),
              ),
              if (selectedTrip != null) ...[
                const SizedBox(height: 8),
                Text(
                  "Trip: ${selectedTrip["id"]} | statut: ${selectedTrip["status"] ?? "-"}",
                ),
              ],
              const SizedBox(height: 8),
              TextField(
                controller: _tripRouteIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Route ID (optionnel UUID)",
                  prefixIcon: Icon(Icons.map_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _tripVehicleIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Vehicle ID (optionnel UUID)",
                  prefixIcon: Icon(Icons.directions_bus_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _tripStatusCtrl,
                decoration: const InputDecoration(
                  labelText: "Trip status",
                  prefixIcon: Icon(Icons.flag_outlined),
                ),
              ),
              const Divider(height: 22),
              Text(
                "Manifest (${_tripManifestShipments.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _manifestShipmentIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Shipment ID a ajouter",
                  prefixIcon: Icon(Icons.add_box_outlined),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _addShipmentToSelectedManifest,
                    icon: const Icon(Icons.playlist_add_check_outlined),
                    label: const Text("Ajouter manifest"),
                  ),
                  OutlinedButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _autoAssignPriorityToSelectedManifest,
                    icon: const Icon(Icons.auto_fix_high_outlined),
                    label: const Text("Auto-assign priorite"),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _tripVehicleCapacityCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: "Vehicle capacity (auto-assign)",
                  prefixIcon: Icon(Icons.inventory_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _tripScanRelayIdCtrl,
                decoration: const InputDecoration(
                  labelText: "Relay ID scan (optionnel)",
                  prefixIcon: Icon(Icons.qr_code_scanner_outlined),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _scanSelectedTripDeparture,
                    icon: const Icon(Icons.flight_takeoff_outlined),
                    label: const Text("Scan depart"),
                  ),
                  FilledButton.icon(
                    onPressed: _selectedTripId.isEmpty
                        ? null
                        : _scanSelectedTripArrival,
                    icon: const Icon(Icons.flight_land_outlined),
                    label: const Text("Scan arrivee"),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (_tripManifestShipments.isEmpty)
                const Text("Aucun colis dans le manifest.")
              else
                ..._tripManifestShipments.take(20).map((shipment) {
                  final shipmentId = shipment["id"]?.toString() ?? "";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.local_shipping_outlined),
                    title: Text(
                      shipment["shipment_no"]?.toString() ?? shipmentId,
                    ),
                    subtitle: Text("status: ${shipment["status"] ?? "-"}"),
                    trailing: OutlinedButton(
                      onPressed: () =>
                          _removeShipmentFromSelectedManifest(shipmentId),
                      child: const Text("Retirer"),
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Gestion Relais",
          icon: Icons.store_mall_directory_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _loadRelayAdminData,
                    icon: const Icon(Icons.sync_outlined),
                    label: const Text("Charger relais"),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => setState(_clearRelayForm),
                    icon: const Icon(Icons.add_business_outlined),
                    label: const Text("Nouveau"),
                  ),
                  OutlinedButton.icon(
                    onPressed: selectedRelay == null
                        ? null
                        : () => _deleteSelectedRelay(),
                    icon: const Icon(Icons.delete_outline),
                    label: const Text("Supprimer"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _selectedRelayId.isEmpty
                    ? null
                    : _selectedRelayId,
                items: _relays
                    .map(
                      (relay) => DropdownMenuItem<String>(
                        value: relay["id"]?.toString() ?? "",
                        child: Text(
                          "${relay["name"] ?? "-"} (${relay["relay_code"] ?? "-"})",
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) async {
                  setState(() => _selectedRelayId = value ?? "");
                  await _loadSelectedRelayDetails();
                },
                decoration: const InputDecoration(
                  labelText: "Relais selectionne",
                  prefixIcon: Icon(Icons.storefront_outlined),
                ),
              ),
              if (selectedRelay != null) ...[
                const SizedBox(height: 8),
                Text(
                  "Type: ${selectedRelay["type"] ?? "-"} | Horaires: ${selectedRelay["opening_hours"] ?? "-"}",
                ),
                if (_relayCapacity != null)
                  Text(
                    "Capacite: ${_relayCapacity!["current_present"]}/${_relayCapacity!["storage_capacity"] ?? "-"}"
                    " | Libre: ${_relayCapacity!["available_slots"] ?? "-"}"
                    " | Full: ${_relayCapacity!["is_full"] == true ? "oui" : "non"}",
                  ),
              ],
              const SizedBox(height: 10),
              Text(
                _editingRelayId.isEmpty ? "Creer un relais" : "Modifier relais",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _relayCodeCtrl,
                decoration: const InputDecoration(
                  labelText: "Code relais",
                  prefixIcon: Icon(Icons.qr_code_2_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _relayNameCtrl,
                decoration: const InputDecoration(
                  labelText: "Nom",
                  prefixIcon: Icon(Icons.home_work_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _relayTypeCtrl,
                decoration: const InputDecoration(
                  labelText: "Type (relay/hub)",
                  prefixIcon: Icon(Icons.category_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _relayOpeningHoursCtrl,
                decoration: const InputDecoration(
                  labelText: "Horaires",
                  prefixIcon: Icon(Icons.schedule_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _relayCapacityCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: "Capacite stockage",
                  prefixIcon: Icon(Icons.inventory_2_outlined),
                ),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _relayIsActive,
                onChanged: (value) => setState(() => _relayIsActive = value),
                title: const Text("Relais actif"),
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _submitRelayForm,
                    icon: const Icon(Icons.save_outlined),
                    label: Text(
                      _editingRelayId.isEmpty
                          ? "Creer relais"
                          : "Mettre a jour",
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: selectedRelay == null
                        ? null
                        : () =>
                              setState(() => _prefillRelayForm(selectedRelay!)),
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text("Editer selection"),
                  ),
                ],
              ),
              const Divider(height: 22),
              Text(
                "Agents rattaches (${_relayAgents.length})",
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _assignAgentId.isEmpty ? null : _assignAgentId,
                items: unassignedAgents
                    .map(
                      (agent) => DropdownMenuItem<String>(
                        value: agent["id"]?.toString() ?? "",
                        child: Text(agent["phone_e164"]?.toString() ?? "-"),
                      ),
                    )
                    .toList(),
                onChanged: (value) =>
                    setState(() => _assignAgentId = value ?? ""),
                decoration: const InputDecoration(
                  labelText: "Agent non assigne",
                  prefixIcon: Icon(Icons.person_add_alt_1_outlined),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _selectedRelayId.isEmpty || _assignAgentId.isEmpty
                    ? null
                    : _assignAgentToSelectedRelay,
                icon: const Icon(Icons.link_outlined),
                label: const Text("Rattacher agent"),
              ),
              const SizedBox(height: 8),
              if (_relayAgents.isEmpty)
                const Text("Aucun agent rattache.")
              else
                ..._relayAgents.map((agent) {
                  final id = agent["id"]?.toString() ?? "";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: const Icon(Icons.badge_outlined),
                    title: Text(agent["phone_e164"]?.toString() ?? "-"),
                    subtitle: Text(id),
                    trailing: OutlinedButton(
                      onPressed: () => _unassignAgentFromSelectedRelay(id),
                      child: const Text("Detacher"),
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _sectionCard(
          title: "Backoffice Compact",
          icon: Icons.dashboard_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _loadBackofficeOverview,
                    icon: const Icon(Icons.query_stats),
                    label: const Text("Charger KPI backoffice"),
                  ),
                  FilledButton.icon(
                    onPressed: _loadServerSyncConflictIncidents,
                    icon: const Icon(Icons.rule_folder_outlined),
                    label: const Text("Charger sync_conflict"),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _syncConflictStatusFilter,
                items: const [
                  DropdownMenuItem(value: "open", child: Text("Statut: open")),
                  DropdownMenuItem(
                    value: "investigating",
                    child: Text("Statut: investigating"),
                  ),
                  DropdownMenuItem(
                    value: "resolved",
                    child: Text("Statut: resolved"),
                  ),
                  DropdownMenuItem(value: "all", child: Text("Statut: all")),
                ],
                onChanged: (value) async {
                  if (value == null) return;
                  setState(() => _syncConflictStatusFilter = value);
                  await _loadServerSyncConflictIncidents();
                },
                decoration: const InputDecoration(
                  labelText: "Filtre statut incident",
                  prefixIcon: Icon(Icons.filter_alt_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _syncIncidentShipmentFilterCtrl,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: "Recherche shipment_id",
                  prefixIcon: Icon(Icons.search_outlined),
                ),
              ),
              const SizedBox(height: 10),
              if (_overview != null) ...[
                Text("shipments_total: ${_overview!["shipments_total"]}"),
                Text("trips_in_progress: ${_overview!["trips_in_progress"]}"),
                Text("incidents_open: ${_overview!["incidents_open"]}"),
                Text(
                  "notifications_pending: ${_overview!["notifications_pending"]}",
                ),
                Text(
                  "auto_assign_acceptance_rate_24h: ${_overview!["auto_assign_acceptance_rate_24h"]}%",
                ),
              ],
              const SizedBox(height: 10),
              if (filteredSyncIncidents.isEmpty)
                const Text("Aucun incident sync_conflict pour ce filtre.")
              else
                ...filteredSyncIncidents.take(20).map((incident) {
                  final incidentId = incident["id"]?.toString() ?? "-";
                  final shipmentId = incident["shipment_id"]?.toString() ?? "-";
                  final status = incident["status"]?.toString() ?? "-";
                  final description =
                      incident["description"]?.toString() ?? "No description";
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    onTap: () => _showIncidentHistory(incidentId),
                    leading: const Icon(Icons.crisis_alert_outlined),
                    title: Text("Incident $incidentId"),
                    subtitle: Text(
                      "shipment: $shipmentId | status: $status\n$description",
                    ),
                    trailing: FilledButton(
                      onPressed: () =>
                          _resolveServerSyncConflictIncident(incident),
                      child: const Text("Resolve"),
                    ),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _buildOfflineQueueCard(),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = _rolePages();
    final destinations = _roleDestinations();
    final selectedIndex = _tabIndex >= pages.length ? 0 : _tabIndex;

    return Scaffold(
      appBar: AppBar(
        title: Text("Logix Mobile (${widget.userType})"),
        actions: [
          IconButton(
            onPressed: _syncing ? null : _syncNow,
            icon: const Icon(Icons.sync),
            tooltip: "Synchroniser",
          ),
          IconButton(
            onPressed: widget.onLogout,
            icon: const Icon(Icons.logout),
            tooltip: "Logout",
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.black.withValues(alpha: 0.06)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                _statusChip(
                  icon: _online
                      ? Icons.cloud_done_outlined
                      : Icons.cloud_off_outlined,
                  label: _online ? "Online" : "Offline",
                  color: _online ? AppTheme.brandPrimary : Colors.red,
                ),
                const SizedBox(width: 8),
                _statusChip(
                  icon: Icons.queue_outlined,
                  label: "Queue ${_queueStats["total"]}",
                  color: AppTheme.brandSecondary,
                ),
                const SizedBox(width: 8),
                _statusChip(
                  icon: Icons.error_outline,
                  label: "Fail ${_queueStats["failed"]}",
                  color: Colors.orange,
                ),
              ],
            ),
          ),
          if (_syncMessage.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(_syncMessage),
              ),
            ),
          Expanded(
            child: IndexedStack(index: selectedIndex, children: pages),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (index) => setState(() => _tabIndex = index),
        destinations: destinations,
      ),
    );
  }
}
