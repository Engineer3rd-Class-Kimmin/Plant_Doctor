class AppServerConfig {
  const AppServerConfig._();

  static const String baseUrl = String.fromEnvironment(
    'PLANT_DOCTOR_SERVER_URL',
    defaultValue: 'http://127.0.0.1:8001',
  );
}
