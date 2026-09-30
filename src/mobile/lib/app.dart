import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/theme/app_theme.dart';
import 'features/analyzing/presentation/analyzing_screen.dart';
import 'features/result/presentation/result_screen.dart';
import 'features/host_selection/presentation/crop_selection_screen.dart';
import 'features/navigation/presentation/main_navigation_screen.dart';
import 'features/splash/presentation/splash_screen.dart';
import 'core/navigation/app_route_observer.dart';

class PlantDoctorApp extends StatelessWidget {
  const PlantDoctorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Plant Doctor',
      debugShowCheckedModeBanner: false,
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      supportedLocales: const [
        Locale('af'),
        Locale('am'),
        Locale('ar'),
        Locale('az'),
        Locale('be'),
        Locale('bg'),
        Locale('bn'),
        Locale('bs'),
        Locale('ca'),
        Locale('cs'),
        Locale('cy'),
        Locale('da'),
        Locale('de'),
        Locale('el'),
        Locale('en'),
        Locale('es'),
        Locale('et'),
        Locale('eu'),
        Locale('fa'),
        Locale('fi'),
        Locale('fr'),
        Locale('ga'),
        Locale('gl'),
        Locale('gu'),
        Locale('he'),
        Locale('hi'),
        Locale('hr'),
        Locale('hu'),
        Locale('hy'),
        Locale('id'),
        Locale('is'),
        Locale('it'),
        Locale('ja'),
        Locale('ka'),
        Locale('kk'),
        Locale('km'),
        Locale('kn'),
        Locale('ko'),
        Locale('ky'),
        Locale('lo'),
        Locale('lt'),
        Locale('lv'),
        Locale('mk'),
        Locale('ml'),
        Locale('mn'),
        Locale('mr'),
        Locale('ms'),
        Locale('my'),
        Locale('nb'),
        Locale('ne'),
        Locale('nl'),
        Locale('nn'),
        Locale('pa'),
        Locale('pl'),
        Locale('ps'),
        Locale('pt'),
        Locale('ro'),
        Locale('ru'),
        Locale('si'),
        Locale('sk'),
        Locale('sl'),
        Locale('so'),
        Locale('sq'),
        Locale('sr'),
        Locale('sv'),
        Locale('sw'),
        Locale('ta'),
        Locale('te'),
        Locale('th'),
        Locale('tr'),
        Locale('uk'),
        Locale('ur'),
        Locale('uz'),
        Locale('vi'),
        Locale('zh'),
      ],
      navigatorObservers: [appRouteObserver],
      theme: AppTheme.lightTheme,
      initialRoute: SplashScreen.routeName,
      routes: {
        SplashScreen.routeName: (_) => const SplashScreen(),
        MainNavigationScreen.routeName: (_) => const MainNavigationScreen(),
        CropSelectionScreen.routeName: (_) => const CropSelectionScreen(),
        AnalyzingScreen.routeName: (_) => const AnalyzingScreen(),
        ResultScreen.routeName: (_) => const ResultScreen(),
      },
    );
  }
}
