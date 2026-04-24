import "package:dio/dio.dart";

import "../config/app_config.dart";

class ApiClient {
  final Dio _dio;

  ApiClient()
    : _dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.apiBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 20),
          headers: {"Content-Type": "application/json"},
        ),
      );

  void setAccessToken(String token) {
    _dio.options.headers["Authorization"] = "Bearer $token";
  }

  void clearAccessToken() {
    _dio.options.headers.remove("Authorization");
  }

  Future<void> requestOtp(String phoneE164) async {
    await _dio.post("/auth/otp/request", data: {"phone_e164": phoneE164});
  }

  Future<Map<String, dynamic>> verifyOtp(String phoneE164, String code) async {
    final response = await _dio.post(
      "/auth/otp/verify",
      data: {"phone_e164": phoneE164, "code": code},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> devLogin(String phoneE164) async {
    final response = await _dio.post(
      "/auth/login",
      data: {"phone_e164": phoneE164},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> me() async {
    final response = await _dio.get("/auth/me");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listUsers({String? role}) async {
    final params = <String, dynamic>{};
    if (role != null && role.isNotEmpty) {
      params["role"] = role;
    }
    final response = await _dio.get("/auth/users", queryParameters: params);
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> myShipments({int limit = 100}) async {
    final response = await _dio.get(
      "/shipments/my",
      queryParameters: {"limit": limit},
    );
    final body = Map<String, dynamic>.from(response.data as Map);
    final items = (body["items"] as List<dynamic>? ?? <dynamic>[]);
    return items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> syncPullShipments({
    String? sinceIso,
    int limit = 200,
  }) async {
    final params = <String, dynamic>{"limit": limit};
    if (sinceIso != null && sinceIso.isNotEmpty) {
      params["since"] = sinceIso;
    }
    final response = await _dio.get(
      "/sync/shipments/pull",
      queryParameters: params,
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> syncPush({
    required List<Map<String, dynamic>> actions,
  }) async {
    final response = await _dio.post("/sync/push", data: {"actions": actions});
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> backofficeOverview() async {
    final response = await _dio.get("/backoffice/overview");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listBackofficeAlerts({
    int delayedHours = 48,
    double relayUtilizationWarn = 0.9,
    int limit = 200,
  }) async {
    final response = await _dio.get(
      "/backoffice/alerts",
      queryParameters: {
        "delayed_hours": delayedHours,
        "relay_utilization_warn": relayUtilizationWarn,
        "limit": limit,
      },
    );
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> listRecentErrors({int limit = 50}) async {
    final response = await _dio.get(
      "/backoffice/errors/recent",
      queryParameters: {"limit": limit},
    );
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> getSmsWorkerStatus() async {
    final response = await _dio.get("/backoffice/sms/worker/status");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> autoDetectIncidents({
    int delayedHours = 48,
    int limit = 200,
  }) async {
    final response = await _dio.post(
      "/backoffice/incidents/auto-detect",
      queryParameters: {"delayed_hours": delayedHours, "limit": limit},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> notifyCriticalAlerts({
    int delayedHours = 48,
    double relayUtilizationWarn = 0.9,
    int throttleMinutes = 30,
    int maxRecipients = 20,
    int maxPerHour = 4,
  }) async {
    final response = await _dio.post(
      "/backoffice/alerts/notify-critical",
      queryParameters: {
        "delayed_hours": delayedHours,
        "relay_utilization_warn": relayUtilizationWarn,
        "throttle_minutes": throttleMinutes,
        "max_recipients": maxRecipients,
        "max_per_hour": maxPerHour,
      },
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listIncidents({
    String? incidentType,
    String? status,
    String? shipmentId,
  }) async {
    final params = <String, dynamic>{};
    if (incidentType != null && incidentType.isNotEmpty) {
      params["incident_type"] = incidentType;
    }
    if (status != null && status.isNotEmpty) {
      params["status"] = status;
    }
    if (shipmentId != null && shipmentId.isNotEmpty) {
      params["shipment_id"] = shipmentId;
    }
    final response = await _dio.get("/incidents", queryParameters: params);
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<List<String>> listIncidentStatuses() async {
    final response = await _dio.get("/incidents/statuses");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => e.toString()).toList();
  }

  Future<Map<String, dynamic>> createIncident({
    required String shipmentId,
    required String incidentType,
    required String description,
  }) async {
    final response = await _dio.post(
      "/incidents",
      data: {
        "shipment_id": shipmentId,
        "incident_type": incidentType,
        "description": description,
      },
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listRelays() async {
    final response = await _dio.get("/relays");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> createRelay(Map<String, dynamic> payload) async {
    final response = await _dio.post("/relays", data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> updateRelay(
    String relayId,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.patch("/relays/$relayId", data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> deleteRelay(String relayId) async {
    await _dio.delete("/relays/$relayId");
  }

  Future<List<Map<String, dynamic>>> listRelayAgents(String relayId) async {
    final response = await _dio.get("/relays/$relayId/agents");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> assignAgentToRelay(
    String relayId,
    String userId,
  ) async {
    final response = await _dio.put("/relays/$relayId/agents/$userId");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> unassignAgentFromRelay(
    String relayId,
    String userId,
  ) async {
    final response = await _dio.delete("/relays/$relayId/agents/$userId");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> getRelayCapacity(String relayId) async {
    final response = await _dio.get("/relays/$relayId/capacity");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listTrips() async {
    final response = await _dio.get("/transport/trips");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> createTrip(Map<String, dynamic> payload) async {
    final response = await _dio.post("/transport/trips", data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> updateTrip(
    String tripId,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.patch(
      "/transport/trips/$tripId",
      data: payload,
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> completeTrip(String tripId) async {
    final response = await _dio.post("/transport/trips/$tripId/complete");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> getTripManifest(String tripId) async {
    final response = await _dio.get("/transport/trips/$tripId/manifest");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> addShipmentToManifest(
    String tripId,
    String shipmentId,
  ) async {
    final response = await _dio.post(
      "/transport/trips/$tripId/manifest/shipments",
      data: {"shipment_id": shipmentId},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> removeShipmentFromManifest(
    String tripId,
    String shipmentId,
  ) async {
    await _dio.delete(
      "/transport/trips/$tripId/manifest/shipments/$shipmentId",
    );
  }

  Future<Map<String, dynamic>> autoAssignPriorityToManifest(
    String tripId, {
    int targetManifestSize = 20,
    int maxAdd = 10,
    int candidateLimit = 500,
    int? vehicleCapacity,
  }) async {
    final payload = <String, dynamic>{
      "target_manifest_size": targetManifestSize,
      "max_add": maxAdd,
      "candidate_limit": candidateLimit,
      "vehicle_capacity": vehicleCapacity,
    };
    final response = await _dio.post(
      "/transport/trips/$tripId/manifest/auto-assign-priority",
      data: payload,
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> scanTripDeparture(
    String tripId, {
    String? relayId,
    String? eventType,
  }) async {
    final response = await _dio.post(
      "/transport/trips/$tripId/scan/departure",
      data: {"relay_id": relayId, "event_type": eventType},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> scanTripArrival(
    String tripId, {
    String? relayId,
    String? eventType,
  }) async {
    final response = await _dio.post(
      "/transport/trips/$tripId/scan/arrival",
      data: {"relay_id": relayId, "event_type": eventType},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> updateIncidentStatus(
    String incidentId,
    String status,
  ) async {
    final response = await _dio.patch(
      "/incidents/$incidentId/status",
      data: {"status": status},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> addIncidentUpdate(
    String incidentId,
    String message,
  ) async {
    final response = await _dio.post(
      "/incidents/$incidentId/updates",
      data: {"message": message},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listIncidentUpdates(
    String incidentId,
  ) async {
    final response = await _dio.get("/incidents/$incidentId/updates");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<List<Map<String, dynamic>>> listClaims({
    String? incidentId,
    String? shipmentId,
    String? status,
  }) async {
    final params = <String, dynamic>{};
    if (incidentId != null && incidentId.isNotEmpty) {
      params["incident_id"] = incidentId;
    }
    if (shipmentId != null && shipmentId.isNotEmpty) {
      params["shipment_id"] = shipmentId;
    }
    if (status != null && status.isNotEmpty) {
      params["status"] = status;
    }
    final response = await _dio.get(
      "/incidents/claims",
      queryParameters: params,
    );
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> createClaim({
    required String incidentId,
    required String shipmentId,
    required num amount,
    required String reason,
  }) async {
    final response = await _dio.post(
      "/incidents/claims",
      data: {
        "incident_id": incidentId,
        "shipment_id": shipmentId,
        "amount": amount,
        "reason": reason,
      },
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<String>> listPaymentStatuses() async {
    final response = await _dio.get("/payments/statuses");
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => e.toString()).toList();
  }

  Future<List<Map<String, dynamic>>> listPayments({
    String? shipmentId,
    String? status,
    String? payerPhone,
  }) async {
    final params = <String, dynamic>{};
    if (shipmentId != null && shipmentId.isNotEmpty) {
      params["shipment_id"] = shipmentId;
    }
    if (status != null && status.isNotEmpty) {
      params["status"] = status;
    }
    if (payerPhone != null && payerPhone.isNotEmpty) {
      params["payer_phone"] = payerPhone;
    }
    final response = await _dio.get("/payments", queryParameters: params);
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> createPayment({
    required String shipmentId,
    required num amount,
    required String payerPhone,
    required String paymentStage,
    required String provider,
  }) async {
    final response = await _dio.post(
      "/payments",
      data: {
        "shipment_id": shipmentId,
        "amount": amount,
        "payer_phone": payerPhone,
        "payment_stage": paymentStage,
        "provider": provider,
      },
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> initiatePayment(
    String paymentId, {
    String? externalRef,
  }) async {
    final response = await _dio.post(
      "/payments/$paymentId/initiate",
      data: {"external_ref": externalRef},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> confirmPayment(
    String paymentId, {
    String? externalRef,
  }) async {
    final response = await _dio.post(
      "/payments/$paymentId/confirm",
      data: {"external_ref": externalRef},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> failPayment(
    String paymentId, {
    required String reason,
  }) async {
    final response = await _dio.post(
      "/payments/$paymentId/fail",
      data: {"reason": reason},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> cancelPayment(String paymentId) async {
    final response = await _dio.post("/payments/$paymentId/cancel");
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> refundPayment(
    String paymentId, {
    required String reason,
  }) async {
    final response = await _dio.post(
      "/payments/$paymentId/refund",
      data: {"reason": reason},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<List<Map<String, dynamic>>> listCommissions({
    String? shipmentId,
    String? paymentId,
  }) async {
    final params = <String, dynamic>{};
    if (shipmentId != null && shipmentId.isNotEmpty) {
      params["shipment_id"] = shipmentId;
    }
    if (paymentId != null && paymentId.isNotEmpty) {
      params["payment_id"] = paymentId;
    }
    final response = await _dio.get(
      "/payments/commissions",
      queryParameters: params,
    );
    final rows = (response.data as List<dynamic>? ?? const []);
    return rows.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> updateClaimStatus({
    required String claimId,
    required String status,
    String? resolutionNote,
    String? refundedPaymentId,
  }) async {
    final response = await _dio.patch(
      "/incidents/claims/$claimId/status",
      data: {
        "status": status,
        "resolution_note": resolutionNote,
        "refunded_payment_id": refundedPaymentId,
      },
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<dynamic> rawRequest({
    required String method,
    required String path,
    required Map<String, dynamic> data,
  }) async {
    final response = await _dio.request(
      path,
      data: data,
      options: Options(method: method),
    );
    return response.data;
  }
}
