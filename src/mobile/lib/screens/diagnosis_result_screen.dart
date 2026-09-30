import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart' hide Text;
import 'package:url_launcher/url_launcher.dart';

import '../core/constants/app_colors.dart';
import '../core/widgets/staggered_reveal.dart';
import '../features/host_selection/presentation/crop_selection_screen.dart';
import '../services/live_segmentation_service.dart';
import '../core/localization/localized_text.dart';
import '../core/localization/unicode_text.dart';

class DiagnosisResultScreen extends StatelessWidget {
  const DiagnosisResultScreen({
    super.key,
    required this.result,
    this.imagePath,
  });

  final DiagnosisResult result;
  final String? imagePath;

  @override
  Widget build(BuildContext context) {
    final double confidencePercent =
        (result.confidence * 100).clamp(0.0, 100.0).toDouble();
    final managementSteps =
        _deduplicateManagementDetails(result.managementSteps);

    return Scaffold(
      backgroundColor: const Color(0xFFF6F7F6),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF6F7F6),
        foregroundColor: AppColors.textPrimary,
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
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final compact = constraints.maxWidth < 360;

                  final information = Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        result.displayName,
                        style: TextStyle(
                          fontSize: compact ? 24 : 28,
                          height: 1.18,
                          fontWeight: FontWeight.w900,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      if (result.displayNameEn.trim().isNotEmpty &&
                          result.displayNameEn != result.displayName) ...[
                        const SizedBox(height: 4),
                        Text(
                          '(${result.displayNameEn})',
                          style: TextStyle(
                            fontSize: compact ? 15 : 17,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          const _StatusChip(
                            label: 'AI 분석 기반',
                            color: Color(0xFFE0F5E5),
                            textColor: AppColors.primary,
                          ),
                          _StatusChip(
                            label: result.severityLabel,
                            color: _severityBackground(result.severityLabel),
                            textColor: _severityText(result.severityLabel),
                          ),
                        ],
                      ),
                    ],
                  );

                  if (compact) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Center(
                          child: _ResultImageCard(
                            imagePath: imagePath,
                            size: 118,
                          ),
                        ),
                        const SizedBox(height: 16),
                        information,
                      ],
                    );
                  }

                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: information),
                      const SizedBox(width: 14),
                      _ResultImageCard(imagePath: imagePath),
                    ],
                  );
                },
              ),
            ),
            const SizedBox(height: 18),
            StaggeredReveal(
              index: 1,
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final confidenceCard = _MetricCard(
                    title: 'AI 신뢰도',
                    value: '${confidencePercent.toStringAsFixed(1)}%',
                    caption: result.confidenceMessage,
                  );
                  return confidenceCard;
                },
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 2,
              child: _NoticeBanner(
                text: result.summaryHeadline,
                subtitle: result.shortSummary,
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 3,
              child: _SectionCard(
                title: 'Plant Doctor의 진단 안내',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _BulletBlock(
                      icon: Icons.visibility_outlined,
                      title: '관찰된 특징',
                      body: result.observationSummary,
                    ),
                    if (result.additionalChecks.isNotEmpty) ...[
                      const Divider(height: 24),
                      _IconListBlock(
                        icon: Icons.search_rounded,
                        title: '추가로 확인해보세요',
                        items: result.additionalChecks,
                      ),
                    ],
                    const Divider(height: 24),
                    _BulletBlock(
                      icon: Icons.warning_amber_rounded,
                      title: '주의 안내',
                      body: result.cautionNote,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 4,
              child: _SectionCard(
                title: '관리 방법',
                child: Column(
                  children: [
                    for (var i = 0; i < managementSteps.length; i++) ...[
                      _ExpandableManagementRow(
                        icon: _managementIcon(i),
                        rawText: managementSteps[i],
                        fallbackDetail: _managementHint(managementSteps[i], i),
                      ),
                      if (i != managementSteps.length - 1)
                        const Divider(height: 16),
                    ],
                    if (managementSteps.isEmpty)
                      const _ExpandableManagementRow(
                        icon: Icons.grass_rounded,
                        rawText: '병든 부위를 먼저 확인하세요 > 병변이 번지는지 관찰하면서 상태를 기록해두세요.',
                        fallbackDetail: '병변이 번지는지 관찰하면서 상태를 기록해두세요.',
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 5,
              child: _SectionCard(
                title: '질병 정보',
                child: Text(
                  result.diseaseInfo,
                  style: const TextStyle(
                    height: 1.6,
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 6,
              child: _SectionCard(
                title: '예방 방법',
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final items = _preventionItems(result);
                    final itemWidth = constraints.maxWidth < 310
                        ? (constraints.maxWidth - 12) / 2
                        : (constraints.maxWidth - 24) / 4;

                    return Wrap(
                      spacing: 8,
                      runSpacing: 14,
                      alignment: WrapAlignment.spaceAround,
                      children: [
                        for (final item in items)
                          SizedBox(
                            width: itemWidth,
                            child: _PreventionItem(
                              icon: item.icon,
                              label: item.label,
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: 14),
            StaggeredReveal(
              index: 7,
              child: _SectionCard(
                title: '분석 정보',
                child: Column(
                  children: [
                    _KeyValueRow(label: '질병 코드', value: result.diseaseName),
                    _KeyValueRow(
                      label: '추정 작물',
                      value: _displayHost(result.hostName),
                    ),
                    _KeyValueRow(
                      label: 'host 보정',
                      value: result.selectionStrategy == 'user_host_locked'
                          ? '적용됨'
                          : '미적용',
                    ),
                    _KeyValueRow(
                      label: 'host 판정 신뢰도',
                      value: result.hostConfidence,
                    ),
                    if (result.hostReason.trim().isNotEmpty)
                      _KeyValueRow(
                        label: 'host 판정 근거',
                        value: result.hostReason,
                      ),
                    _KeyValueRow(label: '안내 출처', value: result.sourceNote),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            StaggeredReveal(
              index: 8,
              child: _SectionCard(
                title: '출처',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (result.sources.isEmpty)
                      const Text(
                        '서버에서 제공된 출처 URL이 없습니다.',
                        style: TextStyle(
                            color: AppColors.textSecondary, fontSize: 12),
                      )
                    else
                      for (final source in result.sources)
                        _SourceLink(source: source),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            StaggeredReveal(
              index: 9,
              child: Column(
                children: [
                  FilledButton.icon(
                    onPressed: () {},
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(54),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    icon: const Icon(Icons.bookmark_border_rounded),
                    label: const Text(
                      '기록에 저장하기',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).pushReplacementNamed(
                      CropSelectionScreen.routeName,
                    ),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(54),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    icon: const Icon(Icons.photo_camera_outlined),
                    label: const Text(
                      '다시 분석하기',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static Color _severityBackground(String label) {
    final normalized = label.toLowerCase();
    if (normalized.contains('위험') ||
        normalized.contains('danger') ||
        normalized.contains('risk') ||
        normalized.contains('severe')) {
      return const Color(0xFFFFE4E2);
    }
    if (normalized.contains('주의') ||
        normalized.contains('caution') ||
        normalized.contains('warning') ||
        normalized.contains('observe') ||
        normalized.contains('moderate')) {
      return const Color(0xFFFFEDBE);
    }
    return const Color(0xFFE8F4EA);
  }

  static Color _severityText(String label) {
    final normalized = label.toLowerCase();
    if (normalized.contains('위험') ||
        normalized.contains('danger') ||
        normalized.contains('risk') ||
        normalized.contains('severe')) {
      return const Color(0xFFC94A3F);
    }
    if (normalized.contains('주의') ||
        normalized.contains('caution') ||
        normalized.contains('warning') ||
        normalized.contains('observe') ||
        normalized.contains('moderate')) {
      return const Color(0xFFB87900);
    }
    return AppColors.primary;
  }

  static IconData _managementIcon(int index) {
    switch (index) {
      case 0:
        return Icons.grass_rounded;
      case 1:
        return Icons.air_rounded;
      case 2:
        return Icons.shield_outlined;
      default:
        return Icons.eco_outlined;
    }
  }

  static List<String> _deduplicateManagementDetails(List<String> steps) {
    final seenDetails = <String>{};
    return steps.map((step) {
      final parts = step.split(RegExp(r'[>→▶▷〉]'));
      if (parts.length < 2) return step;
      final title = parts.first.trim();
      final detail = parts.sublist(1).join(' ').trim();
      final normalized = unicodeSemanticKey(detail);
      if (normalized.isEmpty || !seenDetails.add(normalized)) return title;
      return '$title > $detail';
    }).toList(growable: false);
  }

  static String _managementHint(String text, int index) {
    final value = text.trim().toLowerCase();

    if (value.contains('제거') ||
        value.contains('버리') ||
        value.contains('치워') ||
        value.contains('remove') ||
        value.contains('discard') ||
        value.contains('prune') ||
        value.contains('cut off')) {
      return '제거한 잎과 병든 조직은 다른 식물에 닿지 않게 봉투에 밀봉해 폐기하고, 사용한 가위와 손은 작업 후 깨끗이 씻어주세요.';
    }
    if (value.contains('물') ||
        value.contains('젖') ||
        value.contains('관수') ||
        value.contains('water') ||
        value.contains('wet') ||
        value.contains('irrigat')) {
      return '잎 표면에 물이 오래 남지 않도록 오전에 흙 쪽으로 물을 주고, 화분 받침이나 주변에 고인 물은 바로 비워주세요.';
    }
    if (value.contains('통풍') ||
        value.contains('바람') ||
        value.contains('습') ||
        value.contains('airflow') ||
        value.contains('ventilat') ||
        value.contains('humidity') ||
        value.contains('canopy')) {
      return '잎과 가지 사이를 조금 정리해 공기가 흐르도록 하고, 비닐이나 벽에 너무 붙어 있다면 간격을 확보해주세요.';
    }
    if (value.contains('반점') ||
        value.contains('확인') ||
        value.contains('관찰') ||
        value.contains('기록') ||
        value.contains('spot') ||
        value.contains('check') ||
        value.contains('inspect') ||
        value.contains('observe') ||
        value.contains('monitor') ||
        value.contains('record')) {
      return '같은 위치와 비슷한 조명에서 3~7일 간격으로 사진을 찍어 반점의 개수와 번지는 범위를 비교해 기록해주세요.';
    }
    if (value.contains('약') ||
        value.contains('살균') ||
        value.contains('fungicide') ||
        value.contains('pesticide') ||
        value.contains('spray') ||
        value.contains('chemical')) {
      return '약제를 사용하기 전 작물명과 병해명이 일치하는 등록 제품인지 확인하고, 제품 라벨의 희석 배수와 안전 사용 시기를 지켜주세요.';
    }
    const safeFallbacks = [
      '작업 전후로 손과 도구를 깨끗이 하고, 처리한 병든 조직은 건강한 식물과 분리해주세요.',
      '잎이 오래 젖지 않도록 물주기와 통풍 상태를 조정하고 주변을 청결하게 유지해주세요.',
      '같은 위치를 며칠 간격으로 촬영해 변화를 기록하고, 빠르게 악화되면 지역 농업기술센터에 상담해주세요.',
    ];
    return safeFallbacks[index % safeFallbacks.length];
  }

  static List<_PreventionData> _preventionItems(DiagnosisResult result) {
    final defaults = <_PreventionData>[
      const _PreventionData(Icons.recycling_rounded, '적절한 간격\n유지'),
      const _PreventionData(Icons.water_drop_outlined, '과습 방지'),
      const _PreventionData(Icons.content_cut_rounded, '깨끗한 도구\n사용'),
      const _PreventionData(Icons.search_rounded, '정기적 관찰'),
    ];

    if (result.preventionSteps.isEmpty) {
      return defaults;
    }

    final icons = [
      Icons.recycling_rounded,
      Icons.water_drop_outlined,
      Icons.content_cut_rounded,
      Icons.search_rounded,
    ];

    final items = <_PreventionData>[];
    for (var i = 0; i < result.preventionSteps.length && i < 4; i++) {
      items.add(
          _PreventionData(icons[i], _twoLineLabel(result.preventionSteps[i])));
    }
    while (items.length < 4) {
      items.add(defaults[items.length]);
    }
    return items;
  }

  static String _twoLineLabel(String text) {
    final trimmed = text.trim();
    if (trimmed.length <= 8) return trimmed;
    final words = trimmed.split(' ');
    if (words.length >= 2) {
      final first =
          words.sublist(0, math.min(2, words.length ~/ 2 + 1)).join(' ');
      final second =
          words.sublist(math.min(2, words.length ~/ 2 + 1)).join(' ');
      return second.isEmpty ? first : '$first\n$second';
    }
    final mid = (trimmed.length / 2).round();
    return '${trimmed.substring(0, mid)}\n${trimmed.substring(mid)}';
  }

  static String _displayHost(String host) {
    if (host == 'unknown' || host.trim().isEmpty) return '알 수 없음';
    return host.replaceAll('_', ' ');
  }
}

class _ResultImageCard extends StatelessWidget {
  const _ResultImageCard({
    required this.imagePath,
    this.size = 126,
  });

  final String? imagePath;
  final double size;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(18),
      child: Container(
        width: size,
        height: size,
        color: const Color(0xFFE8F4EA),
        child: imagePath != null && imagePath!.isNotEmpty
            ? Image.file(
                File(imagePath!),
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const _FallbackLeafImage(),
              )
            : const _FallbackLeafImage(),
      ),
    );
  }
}

class _FallbackLeafImage extends StatelessWidget {
  const _FallbackLeafImage();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Icon(
        Icons.eco_rounded,
        color: AppColors.primary,
        size: 48,
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
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
      constraints: const BoxConstraints(minHeight: 144),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              maxLines: 1,
              style: const TextStyle(
                fontSize: 34,
                height: 1.0,
                fontWeight: FontWeight.w900,
                color: AppColors.primary,
              ),
            ),
          ),
          Text(
            caption,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _NoticeBanner extends StatelessWidget {
  const _NoticeBanner({required this.text, required this.subtitle});

  final String text;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primaryTint,
        borderRadius: BorderRadius.circular(15),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: const BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.eco_rounded,
              color: AppColors.primary,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text,
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    height: 1.4,
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

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.title,
    required this.child,
    this.trailingLabel,
  });

  final String title;
  final Widget child;
  final String? trailingLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (trailingLabel != null && trailingLabel!.trim().isNotEmpty)
                Flexible(
                  child: Text(
                    trailingLabel!,
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _BulletBlock extends StatelessWidget {
  const _BulletBlock({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                body,
                style: const TextStyle(
                  height: 1.55,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _IconListBlock extends StatelessWidget {
  const _IconListBlock({
    required this.icon,
    required this.title,
    required this.items,
  });

  final IconData icon;
  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              for (final item in items)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '• ',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                      Expanded(
                        child: Text(
                          item,
                          style: const TextStyle(
                            height: 1.5,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SourceLink extends StatelessWidget {
  const _SourceLink({required this.source});

  final DiagnosisSource source;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () async {
          final uri = Uri.tryParse(source.url);
          if (uri == null ||
              !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('출처 링크를 열 수 없습니다.')),
              );
            }
          }
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.link_rounded,
                  size: 18, color: AppColors.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(source.title,
                        style: const TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(
                      source.url,
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 11.5,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.open_in_new_rounded,
                  size: 17, color: AppColors.textHint),
            ],
          ),
        ),
      ),
    );
  }
}

class _ExpandableManagementRow extends StatefulWidget {
  const _ExpandableManagementRow({
    required this.icon,
    required this.rawText,
    required this.fallbackDetail,
  });

  final IconData icon;
  final String rawText;
  final String fallbackDetail;

  @override
  State<_ExpandableManagementRow> createState() =>
      _ExpandableManagementRowState();
}

class _ExpandableManagementRowState extends State<_ExpandableManagementRow> {
  bool _expanded = false;

  static String _normalizeManagementText(String value) {
    return unicodeSemanticKey(value);
  }

  @override
  Widget build(BuildContext context) {
    final parts = widget.rawText.split(RegExp(r'[>→▶▷〉]'));
    final title = parts.first.trim();
    final candidateDetail =
        parts.length > 1 ? parts.sublist(1).join(' ').trim() : '';
    final fallbackDetail = widget.fallbackDetail.trim();
    final detailSource =
        candidateDetail.isNotEmpty ? candidateDetail : fallbackDetail;

    final normalizedTitle = _normalizeManagementText(title);
    final normalizedDetail = _normalizeManagementText(detailSource);

    // 제목과 완전히 같은 문장만 숨기고, 의미가 일부 겹치더라도
    // 실제 상세 안내는 펼쳤을 때 표시한다.
    final detail =
        normalizedDetail.isEmpty || normalizedDetail == normalizedTitle
            ? ''
            : detailSource;

    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap:
          detail.isEmpty ? null : () => setState(() => _expanded = !_expanded),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(widget.icon, color: AppColors.primary),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                  AnimatedCrossFade(
                    duration: const Duration(milliseconds: 220),
                    crossFadeState: _expanded
                        ? CrossFadeState.showSecond
                        : CrossFadeState.showFirst,
                    firstChild: const SizedBox.shrink(),
                    secondChild: Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(top: 10),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.primaryTint,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        detail,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 12.5,
                          height: 1.55,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            AnimatedRotation(
              turns: _expanded ? 0.25 : 0,
              duration: const Duration(milliseconds: 220),
              child: const Icon(Icons.chevron_right_rounded),
            ),
          ],
        ),
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
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.primary),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                    height: 1.45,
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
  const _PreventionItem({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 50,
          height: 50,
          decoration: const BoxDecoration(
            color: AppColors.primaryTint,
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: AppColors.primary),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            height: 1.35,
          ),
        ),
      ],
    );
  }
}

class _KeyValueRow extends StatelessWidget {
  const _KeyValueRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 4,
            child: Text(
              label,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
          ),
          Expanded(
            flex: 6,
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _PreventionData {
  const _PreventionData(this.icon, this.label);

  final IconData icon;
  final String label;
}
