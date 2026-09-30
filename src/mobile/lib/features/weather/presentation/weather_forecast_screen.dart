import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/localization/localized_text.dart';
import '../../../services/weather_service.dart';

class WeatherForecastScreen extends StatelessWidget {
  const WeatherForecastScreen({
    super.key,
    required this.snapshot,
  });

  final WeatherSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F8F5),
      appBar: AppBar(
        title: const Text('단기 날씨'),
        backgroundColor: const Color(0xFFF6F8F5),
        foregroundColor: AppColors.textPrimary,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.primaryTint,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              children: [
                const Icon(Icons.eco_rounded,
                    color: AppColors.primary, size: 34),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        snapshot.advice,
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w800,
                          fontSize: 17,
                        ),
                      ),
                      if (snapshot.adviceDetail.isNotEmpty) ...[
                        const SizedBox(height: 5),
                        Text(
                          snapshot.adviceDetail,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            height: 1.45,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          for (final item in snapshot.forecast) ...[
            _ForecastCard(item: item),
            const SizedBox(height: 10),
          ],
          if (snapshot.forecast.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(top: 60),
                child: Text('표시할 단기 예보가 없습니다.'),
              ),
            ),
        ],
      ),
    );
  }
}

class _ForecastCard extends StatelessWidget {
  const _ForecastCard({required this.item});

  final WeatherForecastItem item;

  @override
  Widget build(BuildContext context) {
    final dateTime = item.dateTime?.toLocal();
    final month = dateTime?.month;
    final day = dateTime?.day;
    final hour = dateTime?.hour.toString().padLeft(2, '0');
    final timeLabel = dateTime == null ? '예보' : '$month월 $day일 $hour시';
    final humidity = item.humidity ?? '-';
    final rainProbability = item.rainProbability ?? '-';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D000000),
            blurRadius: 10,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          _weatherIcon(item.skyText),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(timeLabel,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(item.skyText,
                    style: const TextStyle(color: AppColors.textSecondary)),
              ],
            ),
          ),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    item.temperature == null
                        ? '-'
                        : '${item.temperature!.toStringAsFixed(0)}°C',
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '습도 $humidity% · 비 $rainProbability%',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _weatherIcon(String sky) {
    final IconData icon;
    if (sky.contains('비') || sky.contains('눈')) {
      icon = Icons.umbrella_rounded;
    } else if (sky.contains('흐림')) {
      icon = Icons.cloud_rounded;
    } else if (sky.contains('구름')) {
      icon = Icons.cloud_queue_rounded;
    } else {
      icon = Icons.wb_sunny_rounded;
    }

    return Container(
      width: 48,
      height: 48,
      decoration: const BoxDecoration(
        color: AppColors.primaryTint,
        shape: BoxShape.circle,
      ),
      child: Icon(icon, color: AppColors.primary),
    );
  }
}
