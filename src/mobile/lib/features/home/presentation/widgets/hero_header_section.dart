import 'package:flutter/material.dart' hide Text;

import '../../../../core/constants/app_colors.dart';
import '../../../../core/localization/localized_text.dart';

class HeroHeaderSection extends StatelessWidget {
  const HeroHeaderSection({
    super.key,
    required this.onStartDiagnosis,
  });

  final VoidCallback onStartDiagnosis;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: SizedBox(
        height: 318,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              height: 232,
              decoration: const BoxDecoration(
                borderRadius: BorderRadius.only(
                  bottomLeft: Radius.circular(38),
                  bottomRight: Radius.circular(38),
                ),
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0B3518), Color(0xFF164D1F), Color(0xFF133215)],
                ),
              ),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Positioned.fill(
                    child: Opacity(
                      opacity: 0.88,
                      child: Image.asset(
                        'assets/images/hero_leaf_blur.png',
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                  Container(
                    decoration: BoxDecoration(
                      borderRadius: const BorderRadius.only(
                        bottomLeft: Radius.circular(38),
                        bottomRight: Radius.circular(38),
                      ),
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          Colors.transparent,
                          Colors.black.withValues(alpha: 0.12),
                          Colors.black.withValues(alpha: 0.18),
                        ],
                      ),
                    ),
                  ),
                  SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [

                          const Spacer(),
                          const Text(
                            '안녕하세요 👋',
                            style: TextStyle(
                              color: Color(0xE6FFFFFF),
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '오늘 식물을\n진단해볼까요?',
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'AI가 5초 안에 식물 건강을 분석합니다.',
                            style: TextStyle(
                              color: Color(0xCFFFFFFF),
                              fontSize: 15,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(height: 22),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Positioned(
              left: 16,
              right: 16,
              bottom: 0,
              child: _StartDiagnosisCard(onTap: onStartDiagnosis),
            ),
          ],
        ),
      ),
    );
  }
}

class _StartDiagnosisCard extends StatelessWidget {
  const _StartDiagnosisCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(34),
        gradient: const LinearGradient(
          colors: [Color(0xFF16692E), Color(0xFF227C36)],
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x3416692E),
            blurRadius: 24,
            offset: Offset(0, 12),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 62,
            height: 62,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(22),
            ),
            child: const Icon(Icons.photo_camera_outlined, color: AppColors.primary, size: 30),
          ),
          const SizedBox(width: 16),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '진단 시작하기',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'AI Camera Diagnosis',
                  style: TextStyle(
                    color: Color(0xC5FFFFFF),
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                SizedBox(height: 10),
                Row(
                  children: [
                    _PillTag(icon: Icons.bolt_rounded, label: '약 5초'),
                    SizedBox(width: 8),
                    _PillTag(icon: Icons.check_rounded, label: '92% 정확도'),
                  ],
                ),
              ],
            ),
          ),
          InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(99),
            child: Container(
              width: 58,
              height: 58,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.10),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white.withValues(alpha: 0.10)),
              ),
              child: const Icon(Icons.chevron_right_rounded, color: Colors.white, size: 34),
            ),
          ),
        ],
      ),
    );
  }
}

class _PillTag extends StatelessWidget {
  const _PillTag({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF98FFB0), size: 14),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
