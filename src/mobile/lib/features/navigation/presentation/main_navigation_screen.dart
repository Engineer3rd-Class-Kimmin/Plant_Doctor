import 'package:flutter/material.dart' hide Text;

import '../../../core/constants/app_colors.dart';
import '../../../core/localization/localized_text.dart';
import '../../home/presentation/home_screen.dart';
import '../../host_selection/presentation/crop_selection_screen.dart';
import '../../dictionary/presentation/disease_dictionary_screen.dart';

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  static const routeName = '/main';

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;

  late final List<Widget> _pages = [
    HomeScreen(
      onStartDiagnosis: _openCamera,
      onGalleryDiagnosis: _openGallery,
      onOpenDictionary: _openDictionary,
      onNavigate: _onTap,
    ),
    const _PlaceholderSection(
      icon: Icons.document_scanner_outlined,
      title: '진단 화면은 카메라 플로우로 연결하세요.',
      subtitle: '이 탭 대신 자동으로 카메라 화면으로 이동하도록 구성할 수 있습니다.',
    ),
    const _PlaceholderSection(
      icon: Icons.menu_book_rounded,
      title: '질병 검색 / 백과사전',
      subtitle: '질병 설명, 작물별 검색, 관리법 리스트가 들어갈 자리입니다.',
    ),
    const _PlaceholderSection(
      icon: Icons.receipt_long_rounded,
      title: '진단 기록',
      subtitle: '서버 또는 로컬 DB와 연결할 진단 히스토리 화면 자리입니다.',
    ),
    const _PlaceholderSection(
      icon: Icons.settings_rounded,
      title: '설정',
      subtitle: '프로필, 알림, 카메라 옵션, 서버 주소 등을 넣을 수 있습니다.',
    ),
  ];

  void _setIndex(int index) {
    setState(() => _currentIndex = index);
  }

  Future<void> _openCamera() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const CropSelectionScreen(
          source: DiagnosisImageSource.camera,
        ),
      ),
    );
  }

  Future<void> _openGallery() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const CropSelectionScreen(
          source: DiagnosisImageSource.gallery,
        ),
      ),
    );
  }

  Future<void> _openDictionary() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const DiseaseDictionaryScreen()),
    );
  }

  void _onTap(int index) {
    if (index == 1) {
      _openCamera();
      return;
    }
    if (index == 2) {
      _openDictionary();
      return;
    }
    _setIndex(index);
  }

  @override
  Widget build(BuildContext context) {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    final navigationHeight =
        (84.0 + (textScale - 1).clamp(0.0, 0.6) * 24).clamp(84.0, 104.0);

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _pages,
      ),
      bottomNavigationBar: _currentIndex == 0
          ? null
          : SafeArea(
              minimum: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: navigationHeight,
                  maxHeight: navigationHeight,
                ),
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(26),
                    border: Border.all(color: AppColors.bottomBarBorder),
                    boxShadow: const [
                      BoxShadow(
                        color: AppColors.shadow,
                        blurRadius: 22,
                        offset: Offset(0, 10),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      _NavItem(
                        icon: Icons.home_rounded,
                        label: '홈',
                        selected: _currentIndex == 0,
                        onTap: () => _onTap(0),
                      ),
                      _NavItem(
                        icon: Icons.camera_alt_outlined,
                        label: '진단',
                        selected: false,
                        onTap: () => _onTap(1),
                      ),
                      _NavItem(
                        icon: Icons.article_outlined,
                        label: '도감',
                        selected: _currentIndex == 2,
                        onTap: () => _onTap(2),
                      ),
                      _NavItem(
                        icon: Icons.access_time_rounded,
                        label: '기록',
                        selected: _currentIndex == 3,
                        onTap: () => _onTap(3),
                      ),
                      _NavItem(
                        icon: Icons.settings_outlined,
                        label: '설정',
                        selected: _currentIndex == 4,
                        onTap: () => _onTap(4),
                      ),
                    ],
                  ),
                ),
              ),
            ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
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
    final color = selected ? AppColors.primary : const Color(0xFF9D9D9D);

    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 72;

            return Padding(
              padding: EdgeInsets.symmetric(
                horizontal: compact ? 2 : 4,
                vertical: 6,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: EdgeInsets.all(compact ? 7 : 9),
                    decoration: BoxDecoration(
                      color:
                          selected ? AppColors.primaryTint : Colors.transparent,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      icon,
                      color: color,
                      size: compact ? 21 : 24,
                    ),
                  ),
                  const SizedBox(height: 3),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      label,
                      maxLines: 1,
                      style: TextStyle(
                        color: color,
                        fontSize: compact ? 10.5 : 12,
                        fontWeight:
                            selected ? FontWeight.w700 : FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _PlaceholderSection extends StatelessWidget {
  const _PlaceholderSection({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: constraints.maxHeight - 40,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(32),
                      boxShadow: const [
                        BoxShadow(
                          color: AppColors.shadow,
                          blurRadius: 20,
                          offset: Offset(0, 8),
                        ),
                      ],
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(icon, size: 48, color: AppColors.primary),
                        const SizedBox(height: 18),
                        Text(
                          title,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          subtitle,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
