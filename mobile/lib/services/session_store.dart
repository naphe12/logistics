import "package:shared_preferences/shared_preferences.dart";

class SessionData {
  final String accessToken;
  final String refreshToken;
  final String phone;
  final String userType;

  const SessionData({
    required this.accessToken,
    required this.refreshToken,
    required this.phone,
    required this.userType,
  });
}

class SessionStore {
  static const _kAccessToken = "access_token";
  static const _kRefreshToken = "refresh_token";
  static const _kPhone = "phone_e164";
  static const _kUserType = "user_type";

  Future<SessionData?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final accessToken = prefs.getString(_kAccessToken);
    if (accessToken == null || accessToken.isEmpty) return null;
    return SessionData(
      accessToken: accessToken,
      refreshToken: prefs.getString(_kRefreshToken) ?? "",
      phone: prefs.getString(_kPhone) ?? "",
      userType: prefs.getString(_kUserType) ?? "customer",
    );
  }

  Future<void> save(SessionData data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAccessToken, data.accessToken);
    await prefs.setString(_kRefreshToken, data.refreshToken);
    await prefs.setString(_kPhone, data.phone);
    await prefs.setString(_kUserType, data.userType);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kAccessToken);
    await prefs.remove(_kRefreshToken);
    await prefs.remove(_kPhone);
    await prefs.remove(_kUserType);
  }
}
