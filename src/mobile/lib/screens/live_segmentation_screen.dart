import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart' hide Text;
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;

import '../features/analyzing/presentation/analyzing_screen.dart';
import '../core/localization/localized_text.dart';
import '../services/live_segmentation_service.dart';

class LiveSegmentationScreen extends StatefulWidget {
  const LiveSegmentationScreen({
    super.key,
    required this.serverBaseUrl,
    required this.selectedHostKo,
    required this.selectedHostId,
  });

  final String serverBaseUrl;
  final String selectedHostKo;
  final String selectedHostId;

  @override
  State<LiveSegmentationScreen> createState() => _LiveSegmentationScreenState();
}

class _LiveSegmentationScreenState extends State<LiveSegmentationScreen>
    with WidgetsBindingObserver {
  static const double _visibleMaskThreshold = 0.0015;
  static const double _captureMaskThreshold = 0.008;
  static const int _requiredStableFrames = 6;
  static const Duration _preCaptureDelay = Duration(milliseconds: 800);

  CameraController? _camera;
  CameraDescription? _cameraDescription;
  late final LiveSegmentationService _segmentation;

  Uint8List? _maskPng;
  Uint8List? _latestFrameJpeg;
  String _guideText = '선택한 작물의 잎을 보여주세요';
  String _detailText = '잎 전체가 화면 안에 들어오도록 맞춰주세요.';
  bool _initializing = true;
  bool _capturing = false;
  bool _capturePending = false;
  bool _serverConnected = false;
  int _stableFrames = 0;
  double _maskRatio = 0;
  bool _lesionVisible = false;

  @override
  void initState() {
    super.initState();
    _guideText = '${widget.selectedHostKo} 잎을 보여주세요';
    WidgetsBinding.instance.addObserver(this);

    unawaited(
      SystemChrome.setPreferredOrientations(
        const [DeviceOrientation.portraitUp],
      ),
    );

    _segmentation = LiveSegmentationService(
      serverBaseUrl: widget.serverBaseUrl,
    );
    unawaited(_initializeCamera());
  }

  Future<void> _initializeCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw StateError('사용 가능한 카메라가 없습니다.');
      }

      final backCamera = cameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      final controller = CameraController(
        backCamera,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );

      await controller.initialize();
      await controller.lockCaptureOrientation(DeviceOrientation.portraitUp);

      try {
        await controller.setFlashMode(FlashMode.off);
        await controller.setExposureMode(ExposureMode.auto);
        await controller.setExposureOffset(0.0);
        await controller.setFocusMode(FocusMode.auto);
      } catch (_) {}

      _cameraDescription = backCamera;
      _camera = controller;

      await _startStream();

      if (!mounted) {
        await controller.dispose();
        return;
      }

      setState(() {
        _initializing = false;
        _guideText = '${widget.selectedHostKo} 잎을 보여주세요';
        _detailText = '잎 전체가 화면 안에 들어오도록 맞춰주세요.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _guideText = '카메라를 시작할 수 없어요';
        _detailText = '$error';
      });
    }
  }

  Future<void> _startStream() async {
    final camera = _camera;
    final description = _cameraDescription;

    if (camera == null ||
        description == null ||
        !camera.value.isInitialized ||
        camera.value.isStreamingImages) {
      return;
    }

    await camera.startImageStream((frame) async {
      if (_capturing || _capturePending) return;

      try {
        final result = await _segmentation.process(
          frame,
          rotationDegrees: description.sensorOrientation,
        );

        if (!mounted || result == null || _capturing || _capturePending) return;
        _handleSegmentation(result);
      } catch (error) {
        if (!mounted || _capturing) return;

        setState(() {
          _serverConnected = false;
          _stableFrames = 0;
          _guideText = '분석 서버를 확인해주세요';
          _detailText = error.toString();
        });
      }
    });
  }

  void _handleSegmentation(LiveSegmentationResult result) {
    final visible = result.maskRatio >= _visibleMaskThreshold;
    final confirmed = result.maskRatio >= _captureMaskThreshold;

    if (confirmed) {
      _stableFrames++;
    } else {
      _stableFrames = 0;
    }

    setState(() {
      _maskPng = result.maskPng;
      _latestFrameJpeg = result.frameJpeg;
      _maskRatio = result.maskRatio;
      _lesionVisible = visible;
      _serverConnected = true;

      if (!visible) {
        _guideText = '식물을 보여주세요';
        _detailText = '잎 전체가 화면 안에 들어오도록 맞춰주세요.';
      } else {
        _guideText = '더 가까이 다가가세요';
        _detailText = confirmed
            ? '병변을 확인하고 있어요. 잠시 그대로 유지해주세요.'
            : '병변이 선명하게 보이도록 화면 중앙에 맞춰주세요.';
      }
    });

    if (_stableFrames >= _requiredStableFrames &&
        !_capturing &&
        !_capturePending) {
      unawaited(_prepareAutomaticCapture());
    }
  }

  Future<void> _prepareAutomaticCapture() async {
    if (_capturing || _capturePending || !mounted) return;

    setState(() {
      _capturePending = true;
      _guideText = '병변을 포착했어요';
      _detailText = '촬영할게요. 잠시 그대로 유지해주세요.';
    });

    // Give the red mask and frame enough time to be visible before capture.
    await Future<void>.delayed(_preCaptureDelay);
    if (!mounted || !_capturePending) return;
    await _captureAndOpenAnalysis();
  }

  Future<void> _captureAndOpenAnalysis() async {
    final camera = _camera;
    if (camera == null || _capturing) return;

    _capturing = true;

    try {
      if (camera.value.isStreamingImages) {
        await camera.stopImageStream();
      }

      XFile photo;
      try {
        final captured = await camera.takePicture();
        final capturedBytes = await captured.readAsBytes();
        if (capturedBytes.isEmpty || img.decodeImage(capturedBytes) == null) {
          throw const FormatException('Camera returned a non-image container.');
        }
        photo = captured;
      } catch (_) {
        final fallbackBytes = _latestFrameJpeg;
        if (fallbackBytes == null || fallbackBytes.isEmpty) {
          rethrow;
        }
        final fallbackPath =
            '${Directory.systemTemp.path}${Platform.pathSeparator}'
            'plant_doctor_capture_${DateTime.now().microsecondsSinceEpoch}.jpg';
        await File(fallbackPath).writeAsBytes(fallbackBytes, flush: true);
        photo = XFile(fallbackPath, mimeType: 'image/jpeg');
      }

      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AnalyzingScreen(
            imagePath: photo.path,
            serverBaseUrl: widget.serverBaseUrl,
            selectedHostKo: widget.selectedHostKo,
            selectedHostId: widget.selectedHostId,
          ),
        ),
      );
    } catch (error) {
      _stableFrames = 0;
      _capturing = false;
      _capturePending = false;

      if (!mounted) return;
      setState(() {
        _guideText = '촬영에 실패했어요';
        _detailText = '$error';
      });

      await Future<void>.delayed(const Duration(seconds: 2));
      if (mounted) {
        setState(() {
          _guideText = '식물을 보여주세요';
          _detailText = '잎 전체가 화면 안에 들어오도록 맞춰주세요.';
        });
      }
      await _startStream();
    }
  }

  Future<void> _manualCapture() async {
    if (_capturing || _camera == null) return;
    if (mounted) {
      setState(() {
        _capturePending = true;
        _guideText = '촬영할게요';
        _detailText = '잠시 그대로 유지해주세요.';
      });
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
    await _captureAndOpenAnalysis();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final camera = _camera;
    if (camera == null || !camera.value.isInitialized) return;

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      if (camera.value.isStreamingImages) {
        unawaited(camera.stopImageStream());
      }
    } else if (state == AppLifecycleState.resumed && !_capturing) {
      unawaited(_startStream());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _segmentation.dispose();

    final camera = _camera;
    if (camera != null) {
      if (camera.value.isStreamingImages) {
        unawaited(camera.stopImageStream());
      }
      unawaited(camera.dispose());
    }

    unawaited(SystemChrome.setPreferredOrientations(DeviceOrientation.values));
    super.dispose();
  }

  Widget _buildFullScreenCamera(CameraController camera) {
    final previewSize = camera.value.previewSize;
    if (previewSize == null) {
      return CameraPreview(camera);
    }

    return Positioned.fill(
      child: ClipRect(
        child: FittedBox(
          fit: BoxFit.cover,
          alignment: Alignment.center,
          child: SizedBox(
            width: previewSize.height,
            height: previewSize.width,
            child: CameraPreview(camera),
          ),
        ),
      ),
    );
  }

  Widget _buildMaskOverlay() {
    final mask = _maskPng;
    if (mask == null || !_lesionVisible) return const SizedBox.shrink();

    return Positioned.fill(
      child: IgnorePointer(
        child: Opacity(
          opacity: _capturePending ? 0.42 : 0.34,
          child: ColorFiltered(
            colorFilter: ColorFilter.mode(
              _capturePending
                  ? const Color(0xFFFF2D2D)
                  : const Color(0xFFFFD400),
              BlendMode.srcIn,
            ),
            child: Image.memory(
              mask,
              fit: BoxFit.cover,
              alignment: Alignment.center,
              gaplessPlayback: true,
              filterQuality: FilterQuality.low,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.42),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.10),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.circle,
                      size: 10,
                      color: _serverConnected
                          ? const Color(0xFFFF3B30)
                          : const Color(0xFFFFB020),
                    ),
                    const SizedBox(width: 7),
                    const Text(
                      'LIVE',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                  decoration: BoxDecoration(
                    color: const Color(0xFF185E20).withOpacity(0.82),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.white.withOpacity(0.12)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.lock_outline_rounded,
                        size: 15,
                        color: Colors.white,
                      ),
                      const SizedBox(width: 5),
                      Flexible(
                        child: Text(
                          widget.selectedHostKo,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              _CircleTopButton(
                icon: Icons.close_rounded,
                onTap: () => Navigator.of(context).pop(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFocusFrame() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final shortestSide = math.min(
          constraints.maxWidth,
          constraints.maxHeight,
        );
        final frameSize = (shortestSide * 0.58).clamp(180.0, 250.0);

        final frameColor = _capturePending
            ? const Color(0xFFFF2D2D)
            : _lesionVisible
                ? const Color(0xFFFFD400)
                : Colors.white;

        return Center(
          child: SizedBox(
            width: frameSize,
            height: frameSize,
            child: Stack(
              alignment: Alignment.center,
              children: [
                _FocusFrame(color: frameColor),
                Icon(
                  Icons.add,
                  size: 16,
                  color: frameColor,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildBottomPanel() {
    return Align(
      alignment: Alignment.bottomCenter,
      child: SafeArea(
        top: false,
        minimum: const EdgeInsets.fromLTRB(18, 0, 18, 12),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final screenHeight = MediaQuery.sizeOf(context).height;
            final compactHeight = screenHeight < 700;
            final captureSize = compactHeight ? 72.0 : 90.0;
            final titleSize = compactHeight ? 22.0 : 30.0;

            return ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: 520,
                maxHeight: constraints.maxHeight,
              ),
              child: SingleChildScrollView(
                reverse: true,
                physics: const ClampingScrollPhysics(),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Text(
                        _guideText,
                        maxLines: 1,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: titleSize,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -0.6,
                        ),
                      ),
                    ),
                    SizedBox(height: compactHeight ? 6 : 10),
                    Text(
                      _detailText,
                      maxLines: compactHeight ? 2 : 3,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.72),
                        fontSize: compactHeight ? 12.5 : 14.5,
                        fontWeight: FontWeight.w500,
                        height: 1.4,
                      ),
                    ),
                    SizedBox(height: compactHeight ? 8 : 14),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.28),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.08),
                        ),
                      ),
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Text(
                          _serverConnected
                              ? '병변 영역 ${(100 * _maskRatio).toStringAsFixed(2)}%'
                              : '서버 연결 대기 중',
                          maxLines: 1,
                          style: TextStyle(
                            color: _serverConnected
                                ? Colors.white.withOpacity(0.88)
                                : const Color(0xFFFFD6A0),
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    SizedBox(height: compactHeight ? 12 : 24),
                    GestureDetector(
                      onTap: _manualCapture,
                      child: SizedBox(
                        width: captureSize,
                        height: captureSize,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color:
                                    const Color(0xFF28E089).withOpacity(0.22),
                                blurRadius: 20,
                              ),
                            ],
                          ),
                          child: Container(
                            margin: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: Colors.white,
                                width: 4,
                              ),
                            ),
                            child: Container(
                              margin: EdgeInsets.all(
                                compactHeight ? 8 : 10,
                              ),
                              decoration: const BoxDecoration(
                                color: Color(0xFFF7F7F7),
                                shape: BoxShape.circle,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                    SizedBox(height: compactHeight ? 6 : 10),
                    Text(
                      _capturing ? '촬영 중' : '자동 촬영 · 수동 촬영 가능',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.80),
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final camera = _camera;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (camera != null && camera.value.isInitialized)
            _buildFullScreenCamera(camera)
          else
            Center(
              child: _initializing
                  ? const CircularProgressIndicator(
                      color: Color(0xFF28E089),
                    )
                  : Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        _detailText,
                        style: const TextStyle(color: Colors.white),
                        textAlign: TextAlign.center,
                      ),
                    ),
            ),
          _buildMaskOverlay(),
          IgnorePointer(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.bottomCenter,
                  end: Alignment.center,
                  colors: [
                    Colors.black.withOpacity(0.64),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
          _buildTopBar(),
          _buildFocusFrame(),
          _buildBottomPanel(),
        ],
      ),
    );
  }
}

class _CircleTopButton extends StatelessWidget {
  const _CircleTopButton({
    required this.icon,
    required this.onTap,
  });

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.42),
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white.withOpacity(0.10)),
        ),
        child: Icon(icon, color: Colors.white, size: 24),
      ),
    );
  }
}

class _FocusFrame extends StatelessWidget {
  const _FocusFrame({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    const stroke = 2.2;
    const length = 40.0;
    const radius = 14.0;

    return Stack(
      children: [
        Positioned(
          top: 0,
          left: 0,
          child: _CornerMark(
            width: length,
            height: length,
            topLeft: Radius.circular(radius),
            borderTop: BorderSide(color: color, width: stroke),
            borderLeft: BorderSide(color: color, width: stroke),
          ),
        ),
        Positioned(
          top: 0,
          right: 0,
          child: _CornerMark(
            width: length,
            height: length,
            topRight: Radius.circular(radius),
            borderTop: BorderSide(color: color, width: stroke),
            borderRight: BorderSide(color: color, width: stroke),
          ),
        ),
        Positioned(
          bottom: 0,
          left: 0,
          child: _CornerMark(
            width: length,
            height: length,
            bottomLeft: Radius.circular(radius),
            borderBottom: BorderSide(color: color, width: stroke),
            borderLeft: BorderSide(color: color, width: stroke),
          ),
        ),
        Positioned(
          bottom: 0,
          right: 0,
          child: _CornerMark(
            width: length,
            height: length,
            bottomRight: Radius.circular(radius),
            borderBottom: BorderSide(color: color, width: stroke),
            borderRight: BorderSide(color: color, width: stroke),
          ),
        ),
      ],
    );
  }
}

class _CornerMark extends StatelessWidget {
  const _CornerMark({
    required this.width,
    required this.height,
    this.topLeft = Radius.zero,
    this.topRight = Radius.zero,
    this.bottomLeft = Radius.zero,
    this.bottomRight = Radius.zero,
    this.borderTop = BorderSide.none,
    this.borderRight = BorderSide.none,
    this.borderBottom = BorderSide.none,
    this.borderLeft = BorderSide.none,
  });

  final double width;
  final double height;
  final Radius topLeft;
  final Radius topRight;
  final Radius bottomLeft;
  final Radius bottomRight;
  final BorderSide borderTop;
  final BorderSide borderRight;
  final BorderSide borderBottom;
  final BorderSide borderLeft;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.only(
          topLeft: topLeft,
          topRight: topRight,
          bottomLeft: bottomLeft,
          bottomRight: bottomRight,
        ),
        border: Border(
          top: borderTop,
          right: borderRight,
          bottom: borderBottom,
          left: borderLeft,
        ),
      ),
    );
  }
}
