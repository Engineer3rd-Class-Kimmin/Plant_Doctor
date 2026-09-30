import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/constants/server_config.dart';
import '../../../core/localization/localized_text.dart';
import '../../../screens/diagnosis_result_screen.dart';
import '../../../services/live_segmentation_service.dart';

class AnalyzingScreen extends StatefulWidget {
  const AnalyzingScreen({
    super.key,
    this.imagePath,
    this.serverBaseUrl = AppServerConfig.baseUrl,
    this.selectedHostKo,
    this.selectedHostId,
  });

  static const routeName = '/analyzing';

  final String? imagePath;
  final String serverBaseUrl;
  final String? selectedHostKo;
  final String? selectedHostId;

  @override
  State<AnalyzingScreen> createState() => _AnalyzingScreenState();
}

class _AnalyzingScreenState extends State<AnalyzingScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _sproutController;
  late final LiveSegmentationService _service;
  Timer? _progressTimer;

  int _activeStep = 0;
  double _progress = 0.05;
  String? _error;
  bool _finished = false;

  final List<String> _steps = const [
    '이미지 품질 확인',
    '잎 영역 인식',
    '병변 탐지',
    '질병 분류',
    'Plant Doctor 설명 생성',
  ];

  @override
  void initState() {
    super.initState();

    _sproutController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 16),
    )..repeat();

    _service = LiveSegmentationService(
      serverBaseUrl: widget.serverBaseUrl,
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startDiagnosis();
    });
  }

  Future<void> _startDiagnosis() async {
    final imagePath = widget.imagePath;
    if (imagePath == null || imagePath.isEmpty) {
      setState(() {
        _error = '분석할 이미지 경로가 없습니다.';
      });
      return;
    }

    setState(() {
      _error = null;
      _finished = false;
      _activeStep = 0;
      _progress = 0.05;
    });

    _startProgressAnimation();

    try {
      final selectedHostId = widget.selectedHostId;
      final selectedHostKo = widget.selectedHostKo;
      if (selectedHostId == null ||
          selectedHostId.isEmpty ||
          selectedHostKo == null ||
          selectedHostKo.isEmpty) {
        throw Exception('선택한 작물 정보가 없습니다. 작물을 다시 선택해주세요.');
      }

      final result = await _service.diagnose(
        XFile(imagePath),
        selectedHostId: selectedHostId,
        selectedHostKo: selectedHostKo,
        locale:
            WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag(),
      );

      _progressTimer?.cancel();

      if (!mounted) return;
      setState(() {
        _activeStep = _steps.length;
        _progress = 1;
        _finished = true;
      });

      await Future<void>.delayed(const Duration(milliseconds: 650));
      if (!mounted) return;

      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => DiagnosisResultScreen(
            result: result,
            imagePath: imagePath,
          ),
        ),
      );
    } catch (error) {
      _progressTimer?.cancel();
      if (!mounted) return;

      setState(() {
        _error = error.toString();
      });
    }
  }

  void _startProgressAnimation() {
    var ticks = 0;

    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(
      const Duration(milliseconds: 450),
      (timer) {
        if (!mounted || _finished || _error != null) {
          timer.cancel();
          return;
        }

        ticks++;
        final nextProgress = (0.06 + ticks * 0.035).clamp(0.0, 0.92);
        final elapsedStage = switch (ticks) {
          < 3 => 0,
          < 6 => 1,
          < 9 => 2,
          < 12 => 3,
          < 16 => 4,
          _ => 5,
        };

        setState(() {
          _progress = nextProgress;
          _activeStep = elapsedStage;
        });
      },
    );
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
    _sproutController.dispose();
    _service.dispose();
    super.dispose();
  }

  int get _percent => (_progress * 100).round();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F7F6),
      appBar: AppBar(
        elevation: 0,
        backgroundColor: const Color(0xFFF6F7F6),
        foregroundColor: AppColors.textPrimary,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 28),
          child: Column(
            children: [
              const Text(
                'AI가 분석 중입니다...',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                '잠시만 기다려주세요.',
                style: TextStyle(
                  fontSize: 16,
                  color: AppColors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              if (widget.selectedHostKo != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                  decoration: BoxDecoration(
                    color: AppColors.primaryTint,
                    borderRadius: BorderRadius.circular(99),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.lock_outline_rounded,
                          size: 17, color: AppColors.primary),
                      const SizedBox(width: 6),
                      Text(
                        '${widget.selectedHostKo} 진단으로 고정됨',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 28),
              _buildAnalysisOrb(),
              const SizedBox(height: 18),
              Text(
                '$_percent%',
                style: const TextStyle(
                  fontSize: 38,
                  fontWeight: FontWeight.w900,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(height: 14),
              ClipRRect(
                borderRadius: BorderRadius.circular(99),
                child: LinearProgressIndicator(
                  value: _progress,
                  minHeight: 8,
                  backgroundColor: const Color(0xFFD9D9D9),
                  valueColor:
                      const AlwaysStoppedAnimation<Color>(AppColors.primary),
                ),
              ),
              const SizedBox(height: 24),
              _buildStepsCard(),
              const SizedBox(height: 18),
              if (_error != null) _buildErrorCard(),
              if (_error == null) _buildTipCard(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAnalysisOrb() {
    return Container(
      width: 192,
      height: 192,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xFFF1F7F1),
        border: Border.all(color: const Color(0xFFA6D6AA)),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 154,
            height: 154,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.88),
                width: 9,
              ),
            ),
          ),
          Container(
            width: 118,
            height: 118,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Color(0x12000000),
                  blurRadius: 18,
                  offset: Offset(0, 6),
                ),
              ],
            ),
            child: Center(
              child: RotationTransition(
                turns: _sproutController,
                child: Image.asset(
                  'assets/images/analyzing_sprout.png',
                  width: 78,
                  height: 78,
                  fit: BoxFit.contain,
                  filterQuality: FilterQuality.high,
                ),
              ),
            ),
          ),
          const Positioned(
            top: 32,
            right: 34,
            child: _OrbitDot(size: 7),
          ),
          const Positioned(
            left: 28,
            bottom: 42,
            child: _OrbitDot(size: 7),
          ),
          const Positioned(
            left: 34,
            top: 62,
            child: _OrbitDot(size: 4.5),
          ),
          const Positioned(
            right: 60,
            bottom: 28,
            child: _OrbitDot(size: 4.5),
          ),
        ],
      ),
    );
  }

  Widget _buildStepsCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E5E5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '분석 단계',
            style: TextStyle(
              fontWeight: FontWeight.w800,
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 12),
          for (var index = 0; index < _steps.length; index++)
            _StepRow(
              label: _steps[index],
              index: index,
              activeStep: _activeStep,
              finished: _finished,
            ),
        ],
      ),
    );
  }

  Widget _buildTipCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F7F1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFD7E9D8)),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.tips_and_updates_outlined, color: AppColors.primary),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '분석 시간이 조금 걸릴 수 있어요',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  '평균 분석 시간은 5~10초 정도 소요됩니다.',
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

  Widget _buildErrorCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF2F0),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFFFD4CF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.error_outline_rounded, color: Color(0xFFD34C40)),
              SizedBox(width: 8),
              Text(
                '분석 중 문제가 발생했어요',
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            _error!,
            style: const TextStyle(
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: _startDiagnosis,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('다시 시도하기'),
          ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.label,
    required this.index,
    required this.activeStep,
    required this.finished,
  });

  final String label;
  final int index;
  final int activeStep;
  final bool finished;

  @override
  Widget build(BuildContext context) {
    final isDone = finished || index < activeStep;
    final isCurrent = !finished && index == activeStep;

    Widget leading;
    String trailing;
    Color trailingColor;

    if (isDone) {
      leading = Container(
        width: 22,
        height: 22,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: AppColors.primary,
        ),
        child: const Icon(
          Icons.check,
          size: 14,
          color: Colors.white,
        ),
      );
      trailing = '완료';
      trailingColor = AppColors.textSecondary;
    } else if (isCurrent) {
      leading = const SizedBox(
        width: 22,
        height: 22,
        child: CircularProgressIndicator(
          strokeWidth: 2.2,
          color: AppColors.primary,
        ),
      );
      trailing = '분석 중';
      trailingColor = AppColors.primary;
    } else {
      leading = Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: const Color(0xFFD3D3D3)),
        ),
      );
      trailing = '대기 중';
      trailingColor = AppColors.textSecondary;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          leading,
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ),
          Text(
            trailing,
            style: TextStyle(
              color: trailingColor,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}

class _OrbitDot extends StatelessWidget {
  const _OrbitDot({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: AppColors.primary,
      ),
    );
  }
}
