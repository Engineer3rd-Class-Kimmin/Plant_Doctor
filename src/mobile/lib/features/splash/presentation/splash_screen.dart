import 'dart:async';

import 'package:flutter/material.dart';

import '../../navigation/presentation/main_navigation_screen.dart';
import '../../shared/widgets/plant_doctor_logo.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  static const routeName = '/';

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();

    _timer = Timer(const Duration(milliseconds: 1800), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed(
        MainNavigationScreen.routeName,
      );
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFFFFFDF8),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 42),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: PlantDoctorLogo(
                size: 230,
                showBackdrop: false,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
