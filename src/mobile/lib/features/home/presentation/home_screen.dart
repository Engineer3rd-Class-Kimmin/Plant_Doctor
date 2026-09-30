import 'dart:math' as math;

import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/localization/localized_text.dart';
import '../../../data/mock/mock_data.dart';
import '../../../core/widgets/staggered_reveal.dart';
import '../../../services/weather_service.dart';
import '../../weather/presentation/weather_forecast_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.onStartDiagnosis,
    required this.onGalleryDiagnosis,
    required this.onOpenDictionary,
    required this.onNavigate,
  });

  final VoidCallback onStartDiagnosis;
  final VoidCallback onGalleryDiagnosis;
  final VoidCallback onOpenDictionary;
  final ValueChanged<int> onNavigate;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final screenWidth = constraints.maxWidth;
            final contentWidth = math.min(screenWidth, 430.0);
            final horizontalPadding =
                screenWidth > 430 ? (screenWidth - contentWidth) / 2 : 18.0;
            final compact = contentWidth < 380;

            return Stack(
              children: [
                SingleChildScrollView(
                  padding: EdgeInsets.fromLTRB(
                      horizontalPadding, 8, horizontalPadding, 132),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      StaggeredReveal(
                        index: 0,
                        child: _HeroHeader(compact: compact),
                      ),
                      StaggeredReveal(
                        index: 3,
                        child: Transform.translate(
                          offset: Offset(0, compact ? -10 : -12),
                          child: _StartDiagnosisCard(
                            compact: compact,
                            onTap: onStartDiagnosis,
                          ),
                        ),
                      ),
                      SizedBox(height: compact ? 2 : 6),
                      Row(
                        children: [
                          Expanded(
                            child: StaggeredReveal(
                              index: 4,
                              child: _QuickActionCard(
                                compact: compact,
                                icon: Icons.grid_view_rounded,
                                iconColor: AppColors.primary,
                                iconBackground: const Color(0xFFEAF4EC),
                                title: '사진으로 진단',
                                subtitle: '갤러리에서 불러오기',
                                onTap: onGalleryDiagnosis,
                              ),
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: StaggeredReveal(
                              index: 5,
                              child: _QuickActionCard(
                                compact: compact,
                                icon: Icons.menu_book_rounded,
                                iconColor: const Color(0xFF2E81B8),
                                iconBackground: const Color(0xFFEDF5FB),
                                title: '질병 검색',
                                subtitle: '식물 백과사전',
                                onTap: onOpenDictionary,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 18),
                      StaggeredReveal(
                        index: 6,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _SectionHeader(
                              title: '최근 진단',
                              actionLabel: '전체 보기',
                              onTap: () => onNavigate(3),
                            ),
                            const SizedBox(height: 12),
                            _RecentDiagnosisCard(
                              compact: compact,
                              onTap: () => onNavigate(3),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                      StaggeredReveal(
                        index: 7,
                        child: _TodayTipCard(
                          compact: compact,
                        ),
                      ),
                    ],
                  ),
                ),
                Positioned(
                  left: horizontalPadding,
                  right: horizontalPadding,
                  bottom: 14,
                  child: _HomeBottomNavigation(
                    onNavigate: onNavigate,
                    onStartDiagnosis: onStartDiagnosis,
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _HeroHeader extends StatelessWidget {
  const _HeroHeader({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final height = compact ? 176.0 : 188.0;

    return Container(
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(30),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(30),
        child: Stack(
          fit: StackFit.expand,
          children: [
            StaggeredReveal(
              index: 0,
              stepDelay: const Duration(milliseconds: 110),
              duration: const Duration(milliseconds: 300),
              offset: const Offset(0, 0.06),
              child: Image.asset(
                'assets/images/home_leaf_dew_header.png',
                fit: BoxFit.cover,
                alignment: Alignment.centerRight,
                filterQuality: FilterQuality.high,
              ),
            ),
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                  colors: [
                    Colors.black.withOpacity(0.58),
                    Colors.black.withOpacity(0.22),
                    Colors.black.withOpacity(0.04),
                  ],
                  stops: const [0.0, 0.58, 1.0],
                ),
              ),
            ),
            Padding(
              padding: EdgeInsets.fromLTRB(
                  compact ? 14 : 16, 12, compact ? 14 : 16, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  StaggeredReveal(
                    index: 1,
                    stepDelay: const Duration(milliseconds: 110),
                    duration: const Duration(milliseconds: 300),
                    offset: const Offset(0, 0.06),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.20),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 30,
                                height: 30,
                                padding: const EdgeInsets.all(4),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(9),
                                ),
                                child: Image.asset(
                                  'assets/images/plant_doctor_top_logo.png',
                                  fit: BoxFit.contain,
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'PlantDoctor',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                  Text(
                                    'AI Plant Assistant',
                                    style: TextStyle(
                                      color: Color(0xDFFFFFFF),
                                      fontSize: 9.5,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const Spacer(),
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.18),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Icon(
                            Icons.notifications_none_rounded,
                            color: Colors.white,
                            size: 23,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  StaggeredReveal(
                    index: 2,
                    stepDelay: const Duration(milliseconds: 110),
                    duration: const Duration(milliseconds: 300),
                    offset: const Offset(0, 0.06),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '오늘 식물을\n진단해볼까요?',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w900,
                            fontSize: compact ? 18 : 20,
                            height: 1.08,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'AI가 10초 안에 식물 건강을 분석합니다.',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.3),
                            fontWeight: FontWeight.w600,
                            fontSize: compact ? 11.5 : 12.5,
                          ),
                        ),
                      ],
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
}

class _StartDiagnosisCard extends StatelessWidget {
  const _StartDiagnosisCard({
    required this.compact,
    required this.onTap,
  });

  final bool compact;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0A3E17).withOpacity(0.30),
            blurRadius: 28,
            spreadRadius: 1,
            offset: const Offset(0, 14),
          ),
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 8,
            spreadRadius: 0,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(999),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Ink(
            height: compact ? 88 : 94,
            padding: EdgeInsets.symmetric(
              horizontal: compact ? 14 : 16,
              vertical: compact ? 8 : 9,
            ),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [
                  const Color(0xFF166A2D).withOpacity(0.70),
                  const Color(0xFF247C39).withOpacity(0.70),
                ],
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: compact ? 50 : 54,
                  height: compact ? 50 : 54,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Icon(
                    Icons.photo_camera_outlined,
                    color: AppColors.primary,
                    size: 25,
                  ),
                ),
                SizedBox(width: compact ? 12 : 15),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '진단 시작하기',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w900,
                          fontSize: compact ? 15.5 : 16.5,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'AI Camera Diagnosis',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.72),
                          fontWeight: FontWeight.w600,
                          fontSize: compact ? 11 : 12,
                        ),
                      ),
                      const SizedBox(height: 5),
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Row(
                          children: const [
                            _InfoChip(
                              icon: Icons.bolt_rounded,
                              iconColor: Color(0xFFFFCF5D),
                              label: '약 10초',
                            ),
                            SizedBox(width: 7),
                            _InfoChip(
                              icon: Icons.check_rounded,
                              iconColor: Color(0xFFB8F06E),
                              label: '92% 정확도',
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  width: compact ? 44 : 48,
                  height: compact ? 44 : 48,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white.withOpacity(0.10),
                    border: Border.all(color: Colors.white.withOpacity(0.15)),
                  ),
                  child: const Icon(
                    Icons.chevron_right_rounded,
                    color: Colors.white,
                    size: 29,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({
    required this.icon,
    required this.iconColor,
    required this.label,
  });

  final IconData icon;
  final Color iconColor;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withOpacity(0.12)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: iconColor),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickActionCard extends StatelessWidget {
  const _QuickActionCard({
    required this.compact,
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final bool compact;
  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(28),
        child: Ink(
          height: compact ? 188 : 200,
          padding:
              EdgeInsets.fromLTRB(compact ? 20 : 24, compact ? 22 : 24, 18, 20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(28),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: compact ? 68 : 72,
                height: compact ? 68 : 72,
                decoration: BoxDecoration(
                  color: iconBackground,
                  borderRadius: BorderRadius.circular(22),
                ),
                child: Icon(icon, color: iconColor, size: compact ? 34 : 36),
              ),
              const Spacer(),
              Text(
                title,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 16 : 17,
                  height: 1.15,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 11 : 12,
                  color: AppColors.textSecondary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.actionLabel,
    required this.onTap,
  });

  final String title;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w900,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        const SizedBox(width: 8),
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            child: Row(
              children: [
                Text(
                  actionLabel,
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(width: 2),
                const Icon(Icons.chevron_right_rounded,
                    color: AppColors.primary, size: 22),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RecentDiagnosisCard extends StatelessWidget {
  const _RecentDiagnosisCard({required this.compact, required this.onTap});

  final bool compact;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final confidence = (recentDiagnosis.confidence * 100).round();

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(30),
        child: Ink(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(30),
          ),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(22),
                  child: SizedBox(
                    width: compact ? 98 : 106,
                    height: compact ? 98 : 106,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.asset(recentDiagnosis.imageAsset,
                            fit: BoxFit.cover),
                        Positioned(
                          left: 8,
                          bottom: 8,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 5),
                            decoration: BoxDecoration(
                              color: Colors.black.withOpacity(0.56),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.circle,
                                    size: 8, color: Color(0xFF6BFF76)),
                                SizedBox(width: 5),
                                Text(
                                  'AI 감지',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
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
                        recentDiagnosis.nameKo,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          fontSize: compact ? 17 : 18,
                          color: AppColors.textPrimary,
                          height: 1.15,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        recentDiagnosis.nameEn,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: compact ? 13 : 14,
                          color: AppColors.textSecondary,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 10,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 7),
                            decoration: BoxDecoration(
                              color: AppColors.dangerSoft,
                              borderRadius: BorderRadius.circular(14),
                              border:
                                  Border.all(color: const Color(0xFFF7D7D7)),
                            ),
                            child: Text(
                              recentDiagnosis.riskLabel,
                              style: const TextStyle(
                                color: AppColors.danger,
                                fontWeight: FontWeight.w800,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          Text(
                            recentDiagnosis.date,
                            style: TextStyle(
                              color: AppColors.textHint,
                              fontSize: compact ? 13 : 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: compact ? 66 : 72,
                      height: compact ? 66 : 72,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox.expand(
                            child: CircularProgressIndicator(
                              value: recentDiagnosis.confidence,
                              strokeWidth: 5.5,
                              backgroundColor: const Color(0xFFF0F0F0),
                              color: const Color(0xFFCC2B2B),
                            ),
                          ),
                          Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                '$confidence%',
                                style: TextStyle(
                                  fontWeight: FontWeight.w900,
                                  fontSize: compact ? 13 : 14,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                              const Text(
                                '신뢰도',
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 10.5,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Icon(Icons.chevron_right_rounded,
                        color: AppColors.textHint, size: 24),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TodayTipCard extends StatefulWidget {
  const _TodayTipCard({required this.compact});

  final bool compact;

  @override
  State<_TodayTipCard> createState() => _TodayTipCardState();
}

class _TodayTipCardState extends State<_TodayTipCard> {
  late Future<WeatherSnapshot> _weatherFuture;

  @override
  void initState() {
    super.initState();
    _weatherFuture = WeatherService().loadWeather();
  }

  String _weatherEmoji(WeatherSnapshot? weather) {
    if (weather == null) return '🌿';
    final sky = weather.skyText;
    final rain = weather.rainProbability ?? 0;
    final temp = weather.temperature;

    if (sky.contains('비/눈')) return '🌨️';
    if (sky.contains('소나기')) return '🌦️';
    if (sky.contains('비') || rain >= 60) return '🌧️';
    if (sky.contains('눈')) return '❄️';
    if (sky.contains('흐림')) return '☁️';
    if (sky.contains('구름')) return '⛅';
    if (temp != null && temp >= 30) return '☀️';
    if (temp != null && temp <= 5) return '🥶';
    if (sky.contains('맑음')) return '☀️';
    return '🌤️';
  }

  void _retry() {
    setState(() {
      _weatherFuture = WeatherService().loadWeather();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<WeatherSnapshot>(
      future: _weatherFuture,
      builder: (context, snapshot) {
        final weather = snapshot.data;
        final loading = snapshot.connectionState == ConnectionState.waiting;
        final hasError = snapshot.hasError;

        return InkWell(
          borderRadius: BorderRadius.circular(30),
          onTap: weather == null
              ? (hasError ? _retry : null)
              : () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => WeatherForecastScreen(snapshot: weather),
                    ),
                  ),
          child: Container(
            height: widget.compact ? 164 : 172,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(30),
            ),
            child: Row(
              children: [
                Container(
                  width: widget.compact ? 102 : 114,
                  decoration: const BoxDecoration(
                    color: Color(0xFFE5F0E6),
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(30),
                      bottomLeft: Radius.circular(30),
                    ),
                  ),
                  child: Center(
                    child: loading
                        ? const SizedBox(
                            width: 30,
                            height: 30,
                            child: CircularProgressIndicator(strokeWidth: 3),
                          )
                        : hasError
                            ? const Icon(
                                Icons.refresh_rounded,
                                size: 52,
                                color: AppColors.primarySoft,
                              )
                            : Text(
                                _weatherEmoji(weather),
                                style: const TextStyle(fontSize: 50),
                              ),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                      widget.compact ? 15 : 18,
                      14,
                      widget.compact ? 14 : 18,
                      14,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.circle,
                                size: 7, color: AppColors.primary),
                            SizedBox(width: 6),
                            Text(
                              '오늘의 AI 추천',
                              style: TextStyle(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w800,
                                fontSize: 15,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          loading
                              ? '현재 위치 날씨를 확인하고 있어요'
                              : hasError
                                  ? '날씨를 불러오지 못했어요'
                                  : weather!.advice,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 15.5,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          loading
                              ? '위치 권한을 허용하면 맞춤 식물 관리 팁을 알려드려요.'
                              : hasError
                                  ? '카드를 눌러 다시 시도해주세요.'
                                  : weather!.adviceDetail,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 10.5,
                            height: 1.35,
                          ),
                        ),
                        const SizedBox(height: 9),
                        Row(
                          children: [
                            _WeatherPlaceholder(
                              icon: Icons.water_drop_outlined,
                              label: weather?.humidity == null
                                  ? '습도 --'
                                  : '습도 ${weather!.humidity}%',
                            ),
                            const SizedBox(width: 14),
                            _WeatherPlaceholder(
                              icon: Icons.thermostat_outlined,
                              label: weather?.temperature == null
                                  ? '온도 --'
                                  : '온도 ${weather!.temperature!.toStringAsFixed(0)}°',
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _WeatherPlaceholder extends StatelessWidget {
  const _WeatherPlaceholder({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 17, color: AppColors.textHint),
        const SizedBox(width: 5),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
      ],
    );
  }
}

class _HomeBottomNavigation extends StatelessWidget {
  const _HomeBottomNavigation({
    required this.onNavigate,
    required this.onStartDiagnosis,
  });

  final ValueChanged<int> onNavigate;
  final VoidCallback onStartDiagnosis;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 92,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.97),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.bottomBarBorder),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _HomeNavItem(
              icon: Icons.home_rounded,
              label: '홈',
              selected: true,
              onTap: () => onNavigate(0)),
          _HomeNavItem(
              icon: Icons.photo_camera_outlined,
              label: '진단',
              selected: false,
              onTap: onStartDiagnosis),
          _HomeNavItem(
              icon: Icons.article_outlined,
              label: '도감',
              selected: false,
              onTap: () => onNavigate(2)),
          _HomeNavItem(
              icon: Icons.access_time_rounded,
              label: '기록',
              selected: false,
              onTap: () => onNavigate(3)),
          _HomeNavItem(
              icon: Icons.settings_outlined,
              label: '설정',
              selected: false,
              onTap: () => onNavigate(4)),
        ],
      ),
    );
  }
}

class _HomeNavItem extends StatelessWidget {
  const _HomeNavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.primary : const Color(0xFFA0A0A0);

    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: selected ? AppColors.primaryTint : Colors.transparent,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 4),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: color,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
