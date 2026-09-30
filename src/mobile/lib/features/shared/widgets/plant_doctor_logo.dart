import 'package:flutter/material.dart';

class PlantDoctorLogo extends StatelessWidget {
  const PlantDoctorLogo({
    super.key,
    this.size = 160,
    this.showBackdrop = false,
  });

  final double size;
  final bool showBackdrop;

  @override
  Widget build(BuildContext context) {
    final logo = SizedBox(
      width: size,
      child: Image.asset(
        'assets/images/plant_doctor_full_logo.png',
        fit: BoxFit.contain,
        filterQuality: FilterQuality.high,
      ),
    );

    if (!showBackdrop) return logo;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.94),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x18000000),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: logo,
    );
  }
}
