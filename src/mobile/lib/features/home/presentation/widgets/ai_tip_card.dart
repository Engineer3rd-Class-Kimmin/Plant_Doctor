import 'package:flutter/material.dart' hide Text;

import '../../../../core/constants/app_colors.dart';
import '../../../../core/localization/localized_text.dart';
import '../../../../core/models/ai_tip.dart';

class AiTipCard extends StatelessWidget {
  const AiTipCard({
    super.key,
    required this.tip,
  });

  final AiTip tip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(30),
        boxShadow: const [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 22,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Text(
                '• 오늘의 AI 추천',
                style: TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w800,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppColors.primaryTint,
                  borderRadius: BorderRadius.circular(22),
                ),
                child: const Icon(Icons.park_rounded, color: AppColors.primary, size: 38),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      tip.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        const Text('💧', style: TextStyle(fontSize: 14)),
                        const SizedBox(width: 6),
                        const Text('습도', style: TextStyle(color: AppColors.textSecondary)),
                        const SizedBox(width: 4),
                        Text(
                          '${tip.humidity}%',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(width: 18),
                        const Text('🌡️', style: TextStyle(fontSize: 14)),
                        const SizedBox(width: 6),
                        const Text('온도', style: TextStyle(color: AppColors.textSecondary)),
                        const SizedBox(width: 4),
                        Text(
                          '${tip.temperature}℃',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    const Row(
                      children: [
                        Text(
                          '더보기',
                          style: TextStyle(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(width: 2),
                        Icon(Icons.chevron_right_rounded, color: AppColors.primary, size: 18),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
