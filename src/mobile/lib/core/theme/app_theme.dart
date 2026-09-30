import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../constants/app_colors.dart';

class AppTheme {
  const AppTheme._();

  static ThemeData get lightTheme {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.background,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.primary,
        brightness: Brightness.light,
      ).copyWith(
        primary: AppColors.primary,
        surface: AppColors.card,
      ),
      appBarTheme: const AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: Colors.transparent,
      ),
      dividerColor: AppColors.border,
      splashFactory: InkRipple.splashFactory,
    );

    final cuteTextTheme = GoogleFonts.juaTextTheme(base.textTheme).copyWith(
      headlineLarge: GoogleFonts.jua(
        fontSize: 40,
        height: 1.1,
        fontWeight: FontWeight.w400,
        color: Colors.white,
      ),
      headlineMedium: GoogleFonts.jua(
        fontSize: 26,
        height: 1.15,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      ),
      titleLarge: GoogleFonts.jua(
        fontSize: 24,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      ),
      titleMedium: GoogleFonts.jua(
        fontSize: 18,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      ),
      bodyLarge: GoogleFonts.jua(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      ),
      bodyMedium: GoogleFonts.jua(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
      ),
      labelLarge: GoogleFonts.jua(fontWeight: FontWeight.w400),
      labelMedium: GoogleFonts.jua(fontWeight: FontWeight.w400),
      labelSmall: GoogleFonts.jua(fontWeight: FontWeight.w400),
    );

    return base.copyWith(textTheme: cuteTextTheme);
  }
}
