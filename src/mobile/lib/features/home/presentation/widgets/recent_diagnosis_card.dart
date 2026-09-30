import 'package:flutter/material.dart' hide Text;

import '../../../../core/constants/app_colors.dart';
import '../../../../core/localization/localized_text.dart';
import '../../../../core/models/diagnosis_record.dart';

class RecentDiagnosisCard extends StatelessWidget {
  const RecentDiagnosisCard({
    super.key,
    required this.record,
  });

  final DiagnosisRecord record;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
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
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(22),
            child: SizedBox(
              width: 108,
              height: 108,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Image.asset(record.imageAsset, fit: BoxFit.cover),
                  Positioned(
                    left: 8,
                    bottom: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.55),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        record.cropName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.nameKo,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 18),
                ),
                const SizedBox(height: 4),
                Text(
                  record.nameEn,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontStyle: FontStyle.italic,
                        color: AppColors.textHint,
                      ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.dangerSoft,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        record.riskLabel,
                        style: const TextStyle(
                          color: AppColors.danger,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      record.date,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 13),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Column(
            children: [
              SizedBox(
                width: 68,
                height: 68,
                child: Stack(
                  fit: StackFit.expand,
                  alignment: Alignment.center,
                  children: [
                    const CircularProgressIndicator(
                      value: 1,
                      strokeWidth: 4,
                      color: Color(0xFFECECEC),
                    ),
                    CircularProgressIndicator(
                      value: record.confidence,
                      strokeWidth: 4,
                      color: AppColors.danger,
                      strokeCap: StrokeCap.round,
                    ),
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          '${(record.confidence * 100).round()}%',
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const Text(
                          '신뢰도',
                          style: TextStyle(
                            fontSize: 10,
                            color: AppColors.textSecondary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              const Icon(Icons.chevron_right_rounded, color: AppColors.textHint),
            ],
          ),
        ],
      ),
    );
  }
}
