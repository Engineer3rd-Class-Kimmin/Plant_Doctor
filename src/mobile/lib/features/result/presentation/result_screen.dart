import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/localization/localized_text.dart';
import '../../../core/widgets/staggered_reveal.dart';
import '../../host_selection/presentation/crop_selection_screen.dart';

const Duration _resultStepDelay = Duration(milliseconds: 110);
const Duration _resultDuration = Duration(milliseconds: 300);
const Offset _resultOffset = Offset(0, 0.06);

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key});

  static const routeName = '/result';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F8F7),
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            onPressed: () {},
            icon: const Icon(Icons.ios_share_rounded),
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
          children: [
            StaggeredReveal(
              index: 0,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '감자 잎마름병',
                          style: TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          '(Early Blight)',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(height: 14),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _StatusChip(
                              label: '곰팡이성 질병',
                              color: Color(0xFFE0F5E5),
                              textColor: AppColors.primary,
                            ),
                            _StatusChip(
                              label: '주의 단계',
                              color: Color(0xFFFFE9B9),
                              textColor: Color(0xFFB87900),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(18),
                    child: Image.asset(
                      'assets/images/diseased_leaf.png',
                      width: 126,
                      height: 126,
                      fit: BoxFit.cover,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 18),

            const StaggeredReveal(
              index: 1,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      title: 'AI 신뢰도',
                      value: '92%',
                      caption: '매우 높은 신뢰도',
                    ),
                  ),
                  SizedBox(width: 12),
                  Expanded(
                    child: _MetricCard(
                      title: '병변 면적',
                      value: '12.5%',
                      caption: '중간 수준',
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            StaggeredReveal(
              index: 2,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: _InfoBanner(),
            ),

            const SizedBox(height: 14),

            StaggeredReveal(
              index: 3,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: _TextInfoCard(),
            ),

            const SizedBox(height: 14),

            StaggeredReveal(
              index: 4,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: _ManagementCard(),
            ),

            const SizedBox(height: 14),

            StaggeredReveal(
              index: 5,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: _PreventionCard(),
            ),

            const SizedBox(height: 14),

            StaggeredReveal(
              index: 6,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: _AnalysisInfoCard(),
            ),

            const SizedBox(height: 16),

            StaggeredReveal(
              index: 7,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: FilledButton.icon(
                onPressed: () {},
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(54),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                icon: const Icon(Icons.bookmark_border_rounded),
                label: const Text(
                  '기록에 저장하기',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 10),

            StaggeredReveal(
              index: 8,
              stepDelay: _resultStepDelay,
              duration: _resultDuration,
              offset: _resultOffset,
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).pushReplacementNamed(
                    CropSelectionScreen.routeName,
                  );
                },
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(54),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                icon: const Icon(Icons.photo_camera_outlined),
                label: const Text(
                  '다시 분석하기',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.label,
    required this.color,
    required this.textColor,
  });

  final String label;
  final Color color;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 7,
      ),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: textColor,
          fontWeight: FontWeight.w700,
          fontSize: 13,
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.caption,
  });

  final String title;
  final String value;
  final String caption;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 140),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D000000),
            blurRadius: 10,
            offset: Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              style: const TextStyle(
              fontSize: 34,
              fontWeight: FontWeight.w900,
              color: AppColors.primary,
            ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            caption,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primaryTint,
        borderRadius: BorderRadius.circular(15),
      ),
      child: const Row(
        children: [
          Icon(
            Icons.eco_rounded,
            color: AppColors.primary,
            size: 28,
          ),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '식물의 잎에서 병변이 확인되었습니다.',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  '초기 단계이므로 빠른 관리가 중요합니다.',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TextInfoCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const _SectionCard(
      title: '질병 정보',
      child: Text(
        '감자 잎마름병은 Alternaria solani 균에 의해 발생하는 곰팡이성 병으로, '
            '잎에 갈색 반점이 생기고 점차 확대되어 잎이 마르며 수확량이 감소합니다.',
        style: TextStyle(
          height: 1.55,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }
}

class _ManagementCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const _SectionCard(
      title: '관리 방법',
      child: Column(
        children: [
          _ActionRow(
            icon: Icons.grass_rounded,
            title: '병든 잎 제거',
            subtitle: '병든 잎과 줄기를 제거하여 전염을 막아주세요.',
          ),
          Divider(),
          _ActionRow(
            icon: Icons.air_rounded,
            title: '통풍 환경 개선',
            subtitle: '식물 간 간격을 충분히 확보하고 통풍을 개선하세요.',
          ),
          Divider(),
          _ActionRow(
            icon: Icons.shield_outlined,
            title: '예방 살균제 사용',
            subtitle: '필요 시 살균제를 사용하여 예방하세요.',
          ),
        ],
      ),
    );
  }
}

class _PreventionCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const _SectionCard(
      title: '예방 방법',
      child: Wrap(
        alignment: WrapAlignment.spaceAround,
        spacing: 8,
        runSpacing: 14,
        children: [
          _PreventionItem(
            icon: Icons.recycling_rounded,
            label: '적절한 간격\n유지',
          ),
          _PreventionItem(
            icon: Icons.water_drop_outlined,
            label: '과습 방지',
          ),
          _PreventionItem(
            icon: Icons.content_cut_rounded,
            label: '깨끗한 도구\n사용',
          ),
          _PreventionItem(
            icon: Icons.search_rounded,
            label: '정기적 관찰',
          ),
        ],
      ),
    );
  }
}

class _AnalysisInfoCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const _SectionCard(
      title: '분석 정보',
      child: Column(
        children: [
          _KeyValueRow(
            label: '분석 날짜',
            value: '2024.06.20 10:30',
          ),
          _KeyValueRow(
            label: '분석 모델',
            value: 'Plant Doctor AI v2.1',
          ),
          _KeyValueRow(
            label: '업데이트',
            value: '2024.06.15',
          ),
          _KeyValueRow(
            label: '출처',
            value: '농촌진흥청 식물병해도감',
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.title,
    required this.child,
  });

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D000000),
            blurRadius: 10,
            offset: Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(
            icon,
            color: AppColors.primary,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded),
        ],
      ),
    );
  }
}

class _PreventionItem extends StatelessWidget {
  const _PreventionItem({
    required this.icon,
    required this.label,
  });

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 70,
      child: Column(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: const BoxDecoration(
              color: AppColors.primaryTint,
              shape: BoxShape.circle,
            ),
            child: Icon(
              icon,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _KeyValueRow extends StatelessWidget {
  const _KeyValueRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                color: AppColors.textSecondary,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              softWrap: true,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
