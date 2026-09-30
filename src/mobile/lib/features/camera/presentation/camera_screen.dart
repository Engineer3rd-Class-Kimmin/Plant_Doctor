import 'package:camera/camera.dart';
import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/localization/localized_text.dart';
import '../../analyzing/presentation/analyzing_screen.dart';

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  static const routeName = '/camera';

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  CameraDescription? _camera;
  String? _errorMessage;
  bool _isInitializing = true;
  bool _isTakingPicture = false;
  bool _flashEnabled = false;
  double _zoomLevel = 1.0;
  double _minZoom = 1.0;
  double _maxZoom = 1.0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initializeCamera();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    if (state == AppLifecycleState.inactive) {
      controller.dispose();
      _controller = null;
    } else if (state == AppLifecycleState.resumed && _camera != null) {
      _initializeController(_camera!);
    }
  }

  Future<void> _initializeCamera() async {
    if (mounted) {
      setState(() {
        _isInitializing = true;
        _errorMessage = null;
      });
    }

    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw CameraException('NoCamera', '사용 가능한 카메라가 없습니다.');
      }

      _camera = cameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      await _initializeController(_camera!);
    } on CameraException catch (error) {
      _handleCameraException(error);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isInitializing = false;
        _errorMessage = '카메라를 시작하지 못했습니다.\n$error';
      });
    }
  }

  Future<void> _initializeController(CameraDescription camera) async {
    final oldController = _controller;
    _controller = null;
    await oldController?.dispose();

    final controller = CameraController(
      camera,
      ResolutionPreset.high,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );

    try {
      await controller.initialize();
      _minZoom = await controller.getMinZoomLevel();
      _maxZoom = await controller.getMaxZoomLevel();
      _zoomLevel = _minZoom.clamp(1.0, _maxZoom).toDouble();
      await controller.setZoomLevel(_zoomLevel);
      await controller.setFlashMode(FlashMode.off);

      if (!mounted) {
        await controller.dispose();
        return;
      }

      setState(() {
        _controller = controller;
        _isInitializing = false;
        _errorMessage = null;
        _flashEnabled = false;
      });
    } on CameraException catch (error) {
      await controller.dispose();
      _handleCameraException(error);
    }
  }

  void _handleCameraException(CameraException error) {
    if (!mounted) return;

    final message = switch (error.code) {
      'CameraAccessDenied' =>
        '카메라 권한이 거부되었습니다.\n앱 권한에서 카메라를 허용해 주세요.',
      'CameraAccessDeniedWithoutPrompt' =>
        '카메라 권한이 꺼져 있습니다.\n휴대폰 설정에서 카메라 권한을 허용해 주세요.',
      'CameraAccessRestricted' => '이 기기에서는 카메라 사용이 제한되어 있습니다.',
      'NoCamera' => '사용 가능한 카메라가 없습니다.',
      _ => '카메라 오류가 발생했습니다.\n${error.description ?? error.code}',
    };

    setState(() {
      _isInitializing = false;
      _errorMessage = message;
    });
  }

  Future<void> _toggleFlash() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    final nextEnabled = !_flashEnabled;
    try {
      await controller.setFlashMode(
        nextEnabled ? FlashMode.torch : FlashMode.off,
      );
      if (mounted) setState(() => _flashEnabled = nextEnabled);
    } on CameraException catch (error) {
      _showSnackBar('플래시를 변경하지 못했습니다: ${error.description ?? error.code}');
    }
  }

  Future<void> _setZoom(double requestedZoom) async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return;

    final zoom = requestedZoom.clamp(_minZoom, _maxZoom).toDouble();
    try {
      await controller.setZoomLevel(zoom);
      if (mounted) setState(() => _zoomLevel = zoom);
    } on CameraException catch (error) {
      _showSnackBar('줌을 변경하지 못했습니다: ${error.description ?? error.code}');
    }
  }

  Future<void> _takePicture() async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        controller.value.isTakingPicture ||
        _isTakingPicture) {
      return;
    }

    setState(() => _isTakingPicture = true);
    try {
      final image = await controller.takePicture();
      if (!mounted) return;

      await Navigator.of(context).pushReplacementNamed(
        AnalyzingScreen.routeName,
        arguments: image.path,
      );
    } on CameraException catch (error) {
      _showSnackBar('사진을 촬영하지 못했습니다: ${error.description ?? error.code}');
    } finally {
      if (mounted) setState(() => _isTakingPicture = false);
    }
  }

  void _showSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          Positioned.fill(child: _buildCameraLayer()),
          SafeArea(
            child: Column(
              children: [
                _buildTopBar(),
                const Expanded(
                  child: Center(
                    child: SizedBox(
                      width: 235,
                      height: 235,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          _FocusFrame(),
                          Icon(Icons.add, color: AppColors.cameraGlow, size: 18),
                        ],
                      ),
                    ),
                  ),
                ),
                _buildBottomControls(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraLayer() {
    final controller = _controller;
    if (_errorMessage != null) {
      return _CameraErrorView(
        message: _errorMessage!,
        onRetry: _initializeCamera,
      );
    }

    if (_isInitializing || controller == null || !controller.value.isInitialized) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.cameraGlow),
      );
    }

    return Center(
      child: SizedBox.expand(
        child: FittedBox(
          fit: BoxFit.cover,
          child: SizedBox(
            width: controller.value.previewSize?.height ?? 1,
            height: controller.value.previewSize?.width ?? 1,
            child: CameraPreview(controller),
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
            ),
            child: const Row(
              children: [
                Icon(Icons.circle, size: 10, color: AppColors.liveRed),
                SizedBox(width: 6),
                Text(
                  'LIVE',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          const Spacer(),
          _RoundActionButton(
            icon: _flashEnabled ? Icons.bolt : Icons.bolt_outlined,
            active: _flashEnabled,
            onTap: _toggleFlash,
          ),
          const SizedBox(width: 10),
          _RoundActionButton(
            icon: Icons.close_rounded,
            onTap: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomControls() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: const Color(0xFF101010),
              borderRadius: BorderRadius.circular(40),
              border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _ZoomChip(
                  label: '1×',
                  selected: _zoomLevel < 1.5,
                  onTap: () => _setZoom(1.0),
                ),
                _ZoomChip(
                  label: '2×',
                  selected: _zoomLevel >= 1.5,
                  onTap: () => _setZoom(2.0),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            '잎을 전체적으로 담아 선명하게 촬영하세요',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '밝은 자연광에서 가장 정확한 결과를 얻을 수 있어요',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.55),
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 28),
          Padding(
            padding: const EdgeInsets.only(bottom: 28),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    width: 54,
                    height: 54,
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Image.asset(
                      'assets/images/potato_thumb.png',
                      fit: BoxFit.cover,
                    ),
                  ),
                ),
                InkWell(
                  onTap: _takePicture,
                  borderRadius: BorderRadius.circular(99),
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.cameraGlow.withValues(alpha: 0.25),
                          blurRadius: 20,
                        ),
                      ],
                    ),
                    child: Container(
                      margin: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 4),
                      ),
                      child: Container(
                        margin: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: Color(0xFFF7F7F7),
                          shape: BoxShape.circle,
                        ),
                        child: _isTakingPicture
                            ? const Padding(
                                padding: EdgeInsets.all(18),
                                child: CircularProgressIndicator(strokeWidth: 3),
                              )
                            : null,
                      ),
                    ),
                  ),
                ),
                _RoundActionButton(
                  icon: Icons.cameraswitch_outlined,
                  size: 54,
                  onTap: _switchCamera,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _switchCamera() async {
    final cameras = await availableCameras();
    if (cameras.length < 2 || _camera == null) return;

    final next = cameras.firstWhere(
      (camera) => camera.lensDirection != _camera!.lensDirection,
      orElse: () => cameras.first,
    );
    _camera = next;
    await _initializeController(next);
  }
}

class _CameraErrorView extends StatelessWidget {
  const _CameraErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.no_photography_outlined, color: Colors.white, size: 64),
            const SizedBox(height: 18),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoundActionButton extends StatelessWidget {
  const _RoundActionButton({
    required this.icon,
    required this.onTap,
    this.size = 44,
    this.active = false,
  });

  final IconData icon;
  final VoidCallback onTap;
  final double size;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(size),
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: active
              ? AppColors.cameraGlow.withValues(alpha: 0.35)
              : Colors.black.withValues(alpha: 0.35),
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
        ),
        child: Icon(icon, color: Colors.white, size: size * 0.45),
      ),
    );
  }
}

class _ZoomChip extends StatelessWidget {
  const _ZoomChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(30),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF333333) : Colors.transparent,
          borderRadius: BorderRadius.circular(30),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

class _FocusFrame extends StatelessWidget {
  const _FocusFrame();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 220,
      height: 220,
      child: Stack(
        children: [
          _FrameCorner(alignment: Alignment.topLeft),
          _FrameCorner(alignment: Alignment.topRight),
          _FrameCorner(alignment: Alignment.bottomLeft),
          _FrameCorner(alignment: Alignment.bottomRight),
        ],
      ),
    );
  }
}

class _FrameCorner extends StatelessWidget {
  const _FrameCorner({required this.alignment});

  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    final top = alignment.y < 0;
    final left = alignment.x < 0;

    return Align(
      alignment: alignment,
      child: SizedBox(
        width: 44,
        height: 44,
        child: CustomPaint(
          painter: _CornerPainter(top: top, left: left),
        ),
      ),
    );
  }
}

class _CornerPainter extends CustomPainter {
  const _CornerPainter({required this.top, required this.left});

  final bool top;
  final bool left;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 2.2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();

    if (top && left) {
      path
        ..moveTo(size.width, 0)
        ..lineTo(0, 0)
        ..lineTo(0, size.height);
    } else if (top && !left) {
      path
        ..moveTo(0, 0)
        ..lineTo(size.width, 0)
        ..lineTo(size.width, size.height);
    } else if (!top && left) {
      path
        ..moveTo(0, 0)
        ..lineTo(0, size.height)
        ..lineTo(size.width, size.height);
    } else {
      path
        ..moveTo(size.width, 0)
        ..lineTo(size.width, size.height)
        ..lineTo(0, size.height);
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _CornerPainter oldDelegate) => false;
}
