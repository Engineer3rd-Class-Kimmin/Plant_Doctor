import 'package:flutter/material.dart' hide Text;
import 'package:image_picker/image_picker.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/constants/server_config.dart';
import '../../../core/localization/localized_text.dart';
import '../../../screens/live_segmentation_screen.dart';
import '../../analyzing/presentation/analyzing_screen.dart';
import '../../../core/widgets/staggered_reveal.dart';

enum DiagnosisImageSource { camera, gallery }

class CropSelectionScreen extends StatefulWidget {
  const CropSelectionScreen({
    super.key,
    this.source = DiagnosisImageSource.camera,
  });

  final DiagnosisImageSource source;

  static const routeName = '/crop-selection';

  @override
  State<CropSelectionScreen> createState() => _CropSelectionScreenState();
}

class _CropSelectionScreenState extends State<CropSelectionScreen> {
  static const List<_CropOption> _crops = [
    _CropOption('가지', 'eggplant', Icons.eco_outlined),
    _CropOption('감귤', 'citrus', Icons.circle_outlined),
    _CropOption('감자', 'potato', Icons.spa_outlined),
    _CropOption('고추', 'pepper', Icons.local_fire_department_outlined),
    _CropOption('당근', 'carrot', Icons.grass_outlined),
    _CropOption('딸기', 'strawberry', Icons.favorite_border_rounded),
    _CropOption('마늘', 'garlic', Icons.filter_vintage_outlined),
    _CropOption('배추', 'napa_cabbage', Icons.eco_rounded),
    _CropOption('벼', 'rice', Icons.grass_rounded),
    _CropOption('복숭아', 'peach', Icons.circle_rounded),
    _CropOption('브로콜리', 'broccoli', Icons.park_outlined),
    _CropOption('블루베리', 'blueberry', Icons.bubble_chart_outlined),
    _CropOption('사과', 'apple', Icons.circle_outlined),
    _CropOption('상추', 'lettuce', Icons.eco_outlined),
    _CropOption('생강', 'ginger', Icons.grass_outlined),
    _CropOption('양배추', 'cabbage', Icons.spa_outlined),
    _CropOption('오이', 'cucumber', Icons.horizontal_rule_rounded),
    _CropOption('옥수수', 'corn', Icons.grass_rounded),
    _CropOption('자두', 'plum', Icons.circle_outlined),
    _CropOption('체리', 'cherry', Icons.bubble_chart_outlined),
    _CropOption('콩', 'soybean', Icons.scatter_plot_outlined),
    _CropOption('토마토', 'tomato', Icons.circle_rounded),
    _CropOption('포도', 'grape', Icons.bubble_chart_rounded),
    _CropOption('호박', 'squash', Icons.circle_outlined),
  ];

  _CropOption? _selected;

  Future<void> _continue() async {
    final selected = _selected;
    if (selected == null) return;

    if (widget.source == DiagnosisImageSource.gallery) {
      final image = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        imageQuality: 95,
        maxWidth: 2400,
        maxHeight: 2400,
      );
      if (!mounted || image == null) return;

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => AnalyzingScreen(
            imagePath: image.path,
            serverBaseUrl: AppServerConfig.baseUrl,
            selectedHostKo: selected.nameKo,
            selectedHostId: selected.hostId,
          ),
        ),
      );
      return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LiveSegmentationScreen(
          serverBaseUrl: AppServerConfig.baseUrl,
          selectedHostKo: selected.nameKo,
          selectedHostId: selected.hostId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F8F5),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF6F8F5),
        foregroundColor: AppColors.textPrimary,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          '진단할 작물 선택',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                children: [
                  StaggeredReveal(
                    index: 0,
                    child: Container(
                      padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: const Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _HeaderLeafIcon(),
                        SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '어떤 식물 진단을 원하세요?',
                                style: TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.w900,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                              SizedBox(height: 8),
                              Text(
                                '작물을 먼저 선택하면 다른 작물의 병으로 잘못 분류되는 것을 줄일 수 있어요.',
                                style: TextStyle(
                                  height: 1.5,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const StaggeredReveal(
                    index: 1,
                    child: Text(
                      '작물 목록',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _crops.length,
                    gridDelegate:
                        const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 132,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                      childAspectRatio: 1.08,
                    ),
                    itemBuilder: (context, index) {
                      final crop = _crops[index];
                      final selected = _selected?.hostId == crop.hostId;
                      return StaggeredReveal(
                        index: index + 2,
                        stepDelay: const Duration(milliseconds: 110),
                        duration: const Duration(milliseconds: 300),
                        offset: const Offset(0, 0.06),
                        child: _CropTile(
                          crop: crop,
                          selected: selected,
                          onTap: () => setState(() => _selected = crop),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 18),
                  StaggeredReveal(
                    index: 8,
                    stepDelay: const Duration(milliseconds: 110),
                    child: Container(
                    padding: const EdgeInsets.all(15),
                    decoration: BoxDecoration(
                      color: AppColors.primaryTint,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.lock_outline_rounded,
                          color: AppColors.primary,
                          size: 21,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            _selected == null
                                ? '작물을 선택한 뒤 카메라로 이동할 수 있어요.'
                                : '${_selected!.nameKo} 진단이 시작되면 결과가 나올 때까지 작물 종류가 고정됩니다.',
                            style: const TextStyle(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w700,
                              height: 1.45,
                            ),
                          ),
                        ),
                      ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 18),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(
                  top: BorderSide(color: AppColors.border),
                ),
              ),
              child: StaggeredReveal(
                index: 9,
                stepDelay: const Duration(milliseconds: 110),
                child: FilledButton.icon(
                onPressed: _selected == null ? null : _continue,
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                icon: Icon(
                  widget.source == DiagnosisImageSource.gallery
                      ? Icons.photo_library_outlined
                      : Icons.photo_camera_outlined,
                ),
                label: Text(
                  _selected == null
                      ? '작물을 선택해주세요'
                      : widget.source == DiagnosisImageSource.gallery
                          ? '${_selected!.nameKo} 사진 선택하기'
                          : '${_selected!.nameKo} 진단 시작하기',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
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

class _CropTile extends StatelessWidget {
  const _CropTile({
    required this.crop,
    required this.selected,
    required this.onTap,
  });

  final _CropOption crop;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: selected ? AppColors.primaryTint : Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? AppColors.primary : AppColors.border,
              width: selected ? 1.8 : 1,
            ),
          ),
          child: Stack(
            children: [
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: selected
                            ? Colors.white
                            : const Color(0xFFF2F7F1),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        crop.icon,
                        color: AppColors.primary,
                        size: 24,
                      ),
                    ),
                    const SizedBox(height: 9),
                    Text(
                      crop.nameKo,
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        color: selected
                            ? AppColors.primary
                            : AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
              if (selected)
                const Positioned(
                  right: 0,
                  top: 0,
                  child: Icon(
                    Icons.check_circle_rounded,
                    color: AppColors.primary,
                    size: 20,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeaderLeafIcon extends StatelessWidget {
  const _HeaderLeafIcon();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 52,
      height: 52,
      decoration: const BoxDecoration(
        color: AppColors.primaryTint,
        shape: BoxShape.circle,
      ),
      child: const Icon(
        Icons.eco_rounded,
        color: AppColors.primary,
        size: 28,
      ),
    );
  }
}

class _CropOption {
  const _CropOption(this.nameKo, this.hostId, this.icon);

  final String nameKo;
  final String hostId;
  final IconData icon;
}
