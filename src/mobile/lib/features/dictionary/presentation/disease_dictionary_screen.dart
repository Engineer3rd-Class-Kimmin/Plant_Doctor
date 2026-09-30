import 'dart:convert';
import 'package:flutter/material.dart' hide Text;
import 'package:http/http.dart' as http;
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/server_config.dart';
import '../../../core/localization/localized_text.dart';

class DiseaseDictionaryScreen extends StatelessWidget {
  const DiseaseDictionaryScreen(
      {super.key, this.serverBaseUrl = AppServerConfig.baseUrl});
  final String serverBaseUrl;

  static const crops = <(String, String, IconData)>[
    ('벼', 'rice', Icons.grass_rounded),
    ('콩', 'soybean', Icons.scatter_plot_outlined),
    ('옥수수', 'corn', Icons.grass_rounded),
    ('사과', 'apple', Icons.circle_outlined),
    ('포도', 'grape', Icons.bubble_chart_rounded),
    ('복숭아', 'peach', Icons.circle_rounded),
    ('자두', 'plum', Icons.circle_outlined),
    ('체리', 'cherry', Icons.bubble_chart_outlined),
    ('감귤', 'citrus', Icons.circle_outlined),
    ('감자', 'potato', Icons.spa_outlined),
    ('토마토', 'tomato', Icons.circle_rounded),
    ('오이', 'cucumber', Icons.horizontal_rule_rounded),
    ('가지', 'eggplant', Icons.eco_outlined),
    ('고추', 'pepper', Icons.local_fire_department_outlined),
    ('배추', 'napa_cabbage', Icons.eco_rounded),
    ('양배추', 'cabbage', Icons.spa_outlined),
    ('브로콜리', 'broccoli', Icons.park_outlined),
    ('마늘', 'garlic', Icons.filter_vintage_outlined),
    ('생강', 'ginger', Icons.grass_outlined),
    ('당근', 'carrot', Icons.grass_outlined),
    ('상추', 'lettuce', Icons.eco_outlined),
    ('딸기', 'strawberry', Icons.favorite_border_rounded),
    ('호박', 'squash', Icons.circle_outlined),
    ('블루베리', 'blueberry', Icons.bubble_chart_outlined),
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: const Color(0xFFF6F8F5),
        appBar: AppBar(
            backgroundColor: const Color(0xFFF6F8F5),
            title: const Text('질병 검색',
                style: TextStyle(fontWeight: FontWeight.w900))),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          const _Card(
              child: Row(children: [
            CircleAvatar(
                radius: 25,
                backgroundColor: Color(0xFFEAF4EC),
                child: Icon(Icons.menu_book_rounded, color: AppColors.primary)),
            SizedBox(width: 14),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text('어떤 작물의 질병을 찾으세요?',
                      style:
                          TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
                  SizedBox(height: 6),
                  Text('작물을 선택하면 로컬 농업 자료를 읽기 쉽게 정리해 보여드려요.',
                      style: TextStyle(
                          color: AppColors.textSecondary, height: 1.45)),
                ])),
          ])),
          const SizedBox(height: 18),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: crops.length,
            gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 132,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
                childAspectRatio: 1.18),
            itemBuilder: (context, i) {
              final crop = crops[i];
              return Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(18),
                    onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) => _DiseaseList(
                                serverBaseUrl: serverBaseUrl,
                                cropName: crop.$1,
                                host: crop.$2))),
                    child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(crop.$3, color: AppColors.primary, size: 29),
                          const SizedBox(height: 8),
                          Text(crop.$1,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w800))
                        ]),
                  ));
            },
          ),
        ]),
      );
}

class _DiseaseList extends StatefulWidget {
  const _DiseaseList(
      {required this.serverBaseUrl,
      required this.cropName,
      required this.host});
  final String serverBaseUrl, cropName, host;
  @override
  State<_DiseaseList> createState() => _DiseaseListState();
}

class _DiseaseListState extends State<_DiseaseList> {
  late final Future<Map<String, dynamic>> future = _getJson(
      '${widget.serverBaseUrl}/v1/dictionary/${widget.host}?locale=${Uri.encodeQueryComponent(_deviceLocale())}',
      30);
  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: const Color(0xFFF6F8F5),
        appBar: AppBar(
            backgroundColor: const Color(0xFFF6F8F5),
            title: Text('${widget.cropName} 질병',
                style: const TextStyle(fontWeight: FontWeight.w900))),
        body: FutureBuilder<Map<String, dynamic>>(
            future: future,
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) return _Error(snap.error.toString());
              final data = snap.data!,
                  diseases = (data['diseases'] as List? ?? const [])
                      .cast<Map<String, dynamic>>();
              final sourceRecordCount = data['source_record_count'];
              final diseaseEvidenceCount = data['disease_evidence_count'];
              final diseaseCount = diseases.length;
              return ListView(padding: const EdgeInsets.all(18), children: [
                Text(
                    '전체 원문 $sourceRecordCount개 · 질병 근거 $diseaseEvidenceCount개 · 질병 $diseaseCount개',
                    style: const TextStyle(color: AppColors.textSecondary)),
                const SizedBox(height: 12),
                for (final d in diseases)
                  _DiseaseTile(
                    disease: d,
                    onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) => _DiseaseDetail(
                                serverBaseUrl: widget.serverBaseUrl,
                                cropName: widget.cropName,
                                host: widget.host,
                                diseaseId: d['disease_id'].toString(),
                                name: d['name'].toString()))),
                  ),
              ]);
            }),
      );
}

class _DiseaseTile extends StatelessWidget {
  const _DiseaseTile({required this.disease, required this.onTap});

  final Map<String, dynamic> disease;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final diseaseId = disease['disease_id'];
    final evidenceCount = disease['evidence_count'];
    return Card(
      elevation: 0,
      color: Colors.white,
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: const CircleAvatar(
          backgroundColor: Color(0xFFEAF4EC),
          child: Icon(Icons.coronavirus_outlined, color: AppColors.primary),
        ),
        title: Text(
          disease['name'].toString(),
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: Text('$diseaseId · 근거 $evidenceCount개'),
        trailing: const Icon(Icons.chevron_right_rounded),
        onTap: onTap,
      ),
    );
  }
}

class _DiseaseDetail extends StatefulWidget {
  const _DiseaseDetail(
      {required this.serverBaseUrl,
      required this.cropName,
      required this.host,
      required this.diseaseId,
      required this.name});
  final String serverBaseUrl, cropName, host, diseaseId, name;
  @override
  State<_DiseaseDetail> createState() => _DiseaseDetailState();
}

class _DiseaseDetailState extends State<_DiseaseDetail> {
  late final Future<Map<String, dynamic>> future = _getJson(
      '${widget.serverBaseUrl}/v1/dictionary/${widget.host}/${widget.diseaseId}?locale=${Uri.encodeQueryComponent(_deviceLocale())}',
      120);
  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: const Color(0xFFF6F8F5),
        appBar: AppBar(
            backgroundColor: const Color(0xFFF6F8F5),
            title: Text(widget.name,
                style: const TextStyle(fontWeight: FontWeight.w900))),
        body: FutureBuilder<Map<String, dynamic>>(
            future: future,
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Center(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 14),
                  Text('RAG 원문을 읽고 쉬운 안내로 정리하고 있어요…')
                ]));
              }
              if (snap.hasError) return _Error(snap.error.toString());
              final data = snap.data!,
                  s = (data['summary'] as Map<String, dynamic>? ?? const {}),
                  sources = (data['sources'] as List? ?? const [])
                      .cast<Map<String, dynamic>>();
              final diseaseId = data['disease_id'];
              final evidenceCount = data['evidence_count'];
              final sourceCount = sources.length;
              return ListView(padding: const EdgeInsets.all(18), children: [
                _Card(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: AspectRatio(
                          aspectRatio: 1.35,
                          child: Image.network(
                            '${widget.serverBaseUrl}/v1/dictionary/${widget.host}/${widget.diseaseId}/image',
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              color: const Color(0xFFEAF4EC),
                              alignment: Alignment.center,
                              child: const Icon(
                                  Icons.image_not_supported_outlined,
                                  color: AppColors.textSecondary,
                                  size: 38),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(data['name'].toString(),
                          style: const TextStyle(
                              fontSize: 25, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 5),
                      Text('${widget.cropName} · $diseaseId',
                          style:
                              const TextStyle(color: AppColors.textSecondary)),
                      const SizedBox(height: 14),
                      Text(s['headline']?.toString() ?? '',
                          style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                              color: AppColors.primary)),
                      const SizedBox(height: 8),
                      Text(s['overview']?.toString() ?? '',
                          style: const TextStyle(height: 1.6)),
                    ])),
                _Section('주요 증상', _strings(s['symptoms'])),
                _Section('원인과 발생 환경', _strings(s['causes'])),
                _Section('전염과 확산', _strings(s['spread'])),
                _Section('관리 방법', _strings(s['management'])),
                _Section('예방 방법', _strings(s['prevention'])),
                const SizedBox(height: 12),
                _Card(
                    child: Text(s['caution']?.toString() ?? '',
                        style: const TextStyle(
                            color: AppColors.textSecondary, height: 1.55))),
                const SizedBox(height: 14),
                Text('정리에 사용한 원문 $evidenceCount개 · 주요 출처 $sourceCount개',
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 7),
                for (final source in sources)
                  Text('• ${source['title']}',
                      style: const TextStyle(
                          color: AppColors.textSecondary, height: 1.5)),
              ]);
            }),
      );
}

Future<Map<String, dynamic>> _getJson(String url, int seconds) async {
  final response =
      await http.get(Uri.parse(url)).timeout(Duration(seconds: seconds));
  if (response.statusCode != 200) {
    throw Exception('자료를 불러오지 못했습니다. (HTTP ${response.statusCode})');
  }
  return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
}

String _deviceLocale() =>
    WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag();

List<String> _strings(dynamic value) => value is List
    ? value.map((e) => e.toString()).where((e) => e.isNotEmpty).toList()
    : const [];

class _Section extends StatelessWidget {
  const _Section(this.title, this.items);
  final String title;
  final List<String> items;
  @override
  Widget build(BuildContext context) => items.isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 12),
          child: _Card(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(title,
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w900)),
                const SizedBox(height: 9),
                for (final item in items)
                  Padding(
                      padding: const EdgeInsets.only(bottom: 7),
                      child:
                          Text('• $item', style: const TextStyle(height: 1.5))),
              ])));
}

class _Card extends StatelessWidget {
  const _Card({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border)),
      child: child);
}

class _Error extends StatelessWidget {
  const _Error(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Center(
      child: Padding(
          padding: const EdgeInsets.all(28),
          child: Text(message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.redAccent))));
}
