import 'package:flutter/material.dart';

import 'app.dart';
import 'core/localization/localized_text.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppTranslationController.instance.initialize();
  runApp(const PlantDoctorApp());
}
