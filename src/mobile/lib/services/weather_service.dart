import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

class WeatherSnapshot {
  const WeatherSnapshot({
    required this.temperature,
    required this.humidity,
    required this.rainProbability,
    required this.skyText,
    required this.advice,
    required this.adviceDetail,
    required this.updatedAt,
    required this.forecast,
  });

  final double? temperature;
  final int? humidity;
  final int? rainProbability;
  final String skyText;
  final String advice;
  final String adviceDetail;
  final DateTime? updatedAt;
  final List<WeatherForecastItem> forecast;
}

class WeatherForecastItem {
  const WeatherForecastItem({
    required this.dateTime,
    required this.temperature,
    required this.humidity,
    required this.rainProbability,
    required this.skyText,
  });

  final DateTime? dateTime;
  final double? temperature;
  final int? humidity;
  final int? rainProbability;
  final String skyText;
}

class WeatherService {
  WeatherService({http.Client? client}) : _client = client ?? http.Client();

  static const String _serviceKey =
      '79u36vTWulj1Slkz8EhUJW8vCGCjOb19XSzRv6J0IsgXdjexOVH%2F9%2Br9LHEFBNo5kGfIR9yQEWvNC39KEYj1XQ%3D%3D';
  static const String _endpoint =
      'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst';

  final http.Client _client;

  Future<Position> requestCurrentPosition() async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) {
      throw Exception('휴대폰 위치 서비스가 꺼져 있습니다. GPS를 켜주세요.');
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      throw Exception('현재 위치의 날씨를 보려면 위치 권한이 필요합니다.');
    }
    if (permission == LocationPermission.deniedForever) {
      throw Exception('위치 권한이 영구 거부되었습니다. 앱 설정에서 위치 권한을 허용해주세요.');
    }

    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.medium,
        timeLimit: Duration(seconds: 12),
      ),
    );
  }

  Future<WeatherSnapshot> loadWeather() async {
    final position = await requestCurrentPosition();
    final grid = _toGrid(position.latitude, position.longitude);
    final base = _latestBaseTime(DateTime.now());

    final uri = Uri.parse(
      '$_endpoint?serviceKey=$_serviceKey&pageNo=1&numOfRows=1000&dataType=JSON'
      '&base_date=${_date(base)}&base_time=${_time(base)}&nx=${grid.$1}&ny=${grid.$2}',
    );

    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) {
        throw Exception('기상청 응답 오류 (HTTP ${response.statusCode})');
      }

      final decoded = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final header = ((decoded['response'] as Map?)?['header'] as Map?) ?? const {};
      if ((header['resultCode'] ?? '').toString() != '00') {
        throw Exception('기상청 오류: ${header['resultMsg'] ?? '알 수 없는 오류'}');
      }

      final responseData = decoded['response'];
      final body = responseData is Map ? responseData['body'] : null;
      final items = body is Map ? body['items'] : null;
      final itemList = items is Map ? items['item'] : null;
      final rawItems = itemList is List ? itemList : const <dynamic>[];

      return _parse(
        rawItems
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList(growable: false),
      );
    } on TimeoutException {
      throw Exception('기상청 날씨 정보를 불러오는 데 시간이 오래 걸리고 있습니다.');
    } on SocketException {
      throw Exception('인터넷 연결을 확인해주세요.');
    } on FormatException {
      throw Exception('기상청 응답 형식을 읽을 수 없습니다.');
    }
  }

  WeatherSnapshot _parse(List<Map<String, dynamic>> items) {
    final grouped = <DateTime, Map<String, String>>{};
    for (final item in items) {
      final date = (item['fcstDate'] ?? '').toString();
      final time = (item['fcstTime'] ?? '').toString();
      if (date.length != 8 || time.length != 4) continue;
      final dt = DateTime.tryParse(
        '${date.substring(0, 4)}-${date.substring(4, 6)}-${date.substring(6, 8)}T${time.substring(0, 2)}:${time.substring(2, 4)}:00',
      );
      if (dt == null) continue;
      grouped.putIfAbsent(dt, () => <String, String>{})[(item['category'] ?? '').toString()] =
          (item['fcstValue'] ?? '').toString();
    }

    final now = DateTime.now();
    final dates = grouped.keys.where((d) => !d.isBefore(now.subtract(const Duration(hours: 1)))).toList()..sort();
    final selected = dates.take(12).toList();
    final forecast = selected.map((dt) {
      final v = grouped[dt]!;
      return WeatherForecastItem(
        dateTime: dt,
        temperature: double.tryParse(v['TMP'] ?? ''),
        humidity: int.tryParse(v['REH'] ?? ''),
        rainProbability: int.tryParse(v['POP'] ?? ''),
        skyText: _sky(v['SKY'], v['PTY']),
      );
    }).toList(growable: false);

    final current = forecast.isNotEmpty ? forecast.first : null;
    final advice = _advice(current);
    return WeatherSnapshot(
      temperature: current?.temperature,
      humidity: current?.humidity,
      rainProbability: current?.rainProbability,
      skyText: current?.skyText ?? '날씨 정보 없음',
      advice: advice.$1,
      adviceDetail: advice.$2,
      updatedAt: DateTime.now(),
      forecast: forecast,
    );
  }

  (String, String) _advice(WeatherForecastItem? item) {
    if (item == null) return ('잎 상태를 직접 확인해주세요', '날씨 자료가 없어 흙의 수분과 잎 상태를 먼저 살펴보세요.');
    final temp = item.temperature;
    final humidity = item.humidity;
    final rain = item.rainProbability ?? 0;

    if (rain >= 60 || item.skyText.contains('비')) {
      return ('오늘은 물주기를 잠시 미뤄주세요', '강수 가능성이 높아 과습과 뿌리 손상을 예방하는 편이 좋습니다.');
    }
    if (temp != null && temp >= 30) {
      return ('한낮을 피해 아침에 물을 주세요', '고온 시간대에는 잎이 데일 수 있어 통풍과 그늘 관리도 함께 해주세요.');
    }
    if (humidity != null && humidity >= 80) {
      return ('통풍을 늘리고 잎을 건조하게 유지하세요', '습도가 높아 곰팡이성 병해가 생기기 쉬운 날씨입니다.');
    }
    if (humidity != null && humidity <= 40) {
      return ('흙이 마르면 천천히 물을 보충하세요', '공기가 건조하므로 잎 끝 마름과 수분 부족을 확인해주세요.');
    }
    if (temp != null && temp <= 5) {
      return ('찬바람을 피하고 보온해주세요', '저온 스트레스를 줄이도록 실내 식물은 창가 냉기를 피해 배치하세요.');
    }
    return ('오늘은 잎 뒷면까지 살펴보세요', '온도와 습도가 비교적 안정적입니다. 해충과 작은 반점을 조기에 확인해주세요.');
  }

  String _sky(String? sky, String? pty) {
    switch (pty) {
      case '1': return '비';
      case '2': return '비/눈';
      case '3': return '눈';
      case '4': return '소나기';
    }
    switch (sky) {
      case '1': return '맑음';
      case '3': return '구름많음';
      case '4': return '흐림';
      default: return '날씨';
    }
  }

  DateTime _latestBaseTime(DateTime now) {
    const hours = [2, 5, 8, 11, 14, 17, 20, 23];
    final available = now.subtract(const Duration(minutes: 15));
    for (final hour in hours.reversed) {
      final candidate = DateTime(available.year, available.month, available.day, hour);
      if (!candidate.isAfter(available)) return candidate;
    }
    final yesterday = available.subtract(const Duration(days: 1));
    return DateTime(yesterday.year, yesterday.month, yesterday.day, 23);
  }

  String _date(DateTime dt) => '${dt.year.toString().padLeft(4, '0')}${dt.month.toString().padLeft(2, '0')}${dt.day.toString().padLeft(2, '0')}';
  String _time(DateTime dt) => '${dt.hour.toString().padLeft(2, '0')}00';

  (int, int) _toGrid(double lat, double lon) {
    const re = 6371.00877;
    const grid = 5.0;
    const slat1 = 30.0;
    const slat2 = 60.0;
    const olon = 126.0;
    const olat = 38.0;
    const xo = 43.0;
    const yo = 136.0;
    const degrad = math.pi / 180.0;

    final reGrid = re / grid;
    final slat1Rad = slat1 * degrad;
    final slat2Rad = slat2 * degrad;
    var sn = math.tan(math.pi * 0.25 + slat2Rad * 0.5) /
        math.tan(math.pi * 0.25 + slat1Rad * 0.5);
    sn = math.log(math.cos(slat1Rad) / math.cos(slat2Rad)) / math.log(sn);
    var sf = math.tan(math.pi * 0.25 + slat1Rad * 0.5);
    sf = (math.pow(sf, sn) * math.cos(slat1Rad) / sn).toDouble();
    var ro = math.tan(math.pi * 0.25 + olat * degrad * 0.5);
    ro = (reGrid * sf / math.pow(ro, sn)).toDouble();
    var ra = math.tan(math.pi * 0.25 + lat * degrad * 0.5);
    ra = (reGrid * sf / math.pow(ra, sn)).toDouble();
    var theta = lon * degrad - olon * degrad;
    if (theta > math.pi) theta -= 2.0 * math.pi;
    if (theta < -math.pi) theta += 2.0 * math.pi;
    theta *= sn;
    return ((ra * math.sin(theta) + xo + 0.5).floor(), (ro - ra * math.cos(theta) + yo + 0.5).floor());
  }
}
