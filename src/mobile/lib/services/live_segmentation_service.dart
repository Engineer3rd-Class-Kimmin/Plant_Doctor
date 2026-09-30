import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:image/image.dart' as img;

import '../core/localization/unicode_text.dart';

class DiagnosisSource {
  const DiagnosisSource({required this.title, required this.url});

  final String title;
  final String url;
}

class LiveSegmentationResult {
  const LiveSegmentationResult({
    required this.maskPng,
    required this.frameJpeg,
    required this.elapsed,
    required this.maskRatio,
  });

  final Uint8List maskPng;
  final Uint8List frameJpeg;
  final Duration elapsed;
  final double maskRatio;
}

class DiagnosisResult {
  const DiagnosisResult({
    required this.diseaseName,
    required this.displayName,
    required this.displayNameEn,
    required this.confidence,
    required this.maskRatio,
    required this.objectMaskRatio,
    required this.lesionObjectRatio,
    required this.gemmaOutput,
    required this.classifierLabel,
    required this.summaryHeadline,
    required this.shortSummary,
    required this.observationSummary,
    required this.diseaseInfo,
    required this.managementSteps,
    required this.preventionSteps,
    required this.additionalChecks,
    required this.cautionNote,
    required this.confidenceMessage,
    required this.severityLabel,
    required this.sourceNote,
    required this.sources,
    required this.hostName,
    required this.hostConfidence,
    required this.hostReason,
    required this.selectionStrategy,
  });

  final String diseaseName;
  final String displayName;
  final String displayNameEn;
  final double confidence;
  final double maskRatio;
  final double objectMaskRatio;
  final double lesionObjectRatio;
  final String gemmaOutput;
  final String classifierLabel;

  final String summaryHeadline;
  final String shortSummary;
  final String observationSummary;
  final String diseaseInfo;
  final List<String> managementSteps;
  final List<String> preventionSteps;
  final List<String> additionalChecks;
  final String cautionNote;
  final String confidenceMessage;
  final String severityLabel;
  final String sourceNote;
  final List<DiagnosisSource> sources;

  final String hostName;
  final String hostConfidence;
  final String hostReason;
  final String selectionStrategy;

  factory DiagnosisResult.fromJson(Map<String, dynamic> json) {
    final summary = (json['summary'] is Map<String, dynamic>)
        ? json['summary'] as Map<String, dynamic>
        : <String, dynamic>{};
    final hostDetection = (json['host_detection'] is Map<String, dynamic>)
        ? json['host_detection'] as Map<String, dynamic>
        : <String, dynamic>{};

    final diseaseName =
        (json['disease_name'] ?? json['classifier_label'] ?? '알 수 없음')
            .toString();

    final displayName = (json['display_name'] ??
            summary['disease_name_ko'] ??
            _humanizeDiseaseLabel(diseaseName))
        .toString();

    final displayNameEn = (json['display_name_en'] ??
            summary['disease_name_en'] ??
            _humanizeDiseaseLabel(diseaseName))
        .toString();

    final rawMaskRatio = _firstNumber(json, const [
          'mask_ratio',
          'lesion_full_image_ratio',
          'segmentation.mask_ratio',
          'segmentation.lesion_full_image_ratio',
          'metrics.mask_ratio',
        ]) ??
        0.0;

    final objectMaskRatio = _firstNumber(json, const [
          'object_mask_ratio',
          'host_object_ratio',
          'plant_object_ratio',
          'segmentation.object_mask_ratio',
          'metrics.object_mask_ratio',
          'area.object_mask_ratio',
        ]) ??
        0.0;

    final explicitObjectRatio = _firstNumber(json, const [
      'lesion_object_ratio',
      'lesion_ratio_in_object',
      'lesion_area_ratio_in_object',
      'segmentation.lesion_object_ratio',
      'metrics.lesion_object_ratio',
      'area.lesion_object_ratio',
    ]);

    // 전체 카메라 면적(mask_ratio)을 오브젝트 기준 병변 면적으로 사용하지 않는다.
    // 서버가 오브젝트 마스크 비율을 제공할 때만 계산한다.
    final lesionObjectRatio = explicitObjectRatio != null
        ? explicitObjectRatio.clamp(0.0, 1.0).toDouble()
        : (objectMaskRatio > 0
            ? (rawMaskRatio / objectMaskRatio).clamp(0.0, 1.0).toDouble()
            : -1.0);

    return DiagnosisResult(
      diseaseName: diseaseName,
      displayName: displayName,
      displayNameEn: displayNameEn,
      confidence: (json['confidence'] as num? ?? 0).toDouble(),
      maskRatio: rawMaskRatio,
      objectMaskRatio: objectMaskRatio,
      lesionObjectRatio: lesionObjectRatio,
      gemmaOutput: (json['gpt_output'] ??
              json['gemma_output'] ??
              'Plant Doctor 응답이 없습니다.')
          .toString(),
      classifierLabel: (json['classifier_label'] ?? '알 수 없음').toString(),
      summaryHeadline: _cleanUserText(
          (summary['headline'] ?? '식물 잎에서 병징이 의심됩니다.').toString()),
      shortSummary: _cleanUserText(
          (summary['short_summary'] ?? 'AI 분석 결과를 바탕으로 병해 가능성을 안내합니다.')
              .toString()),
      observationSummary: _cleanUserText(
          (summary['observation_summary'] ?? '잎에서 병변이 의심되는 부위가 확인되었습니다.')
              .toString()),
      diseaseInfo: _cleanUserText(
          (summary['disease_info'] ?? '질병 정보 요약이 아직 준비되지 않았습니다.').toString()),
      managementSteps: _stringList(summary['management_steps']),
      preventionSteps: _stringList(summary['prevention_steps']),
      additionalChecks: _stringList(summary['additional_checks']),
      cautionNote: _cleanUserText(
          (summary['caution_note'] ?? '모델 결과는 참고용이며, 증상이 심해지면 전문가 확인이 필요합니다.')
              .toString()),
      confidenceMessage: _cleanUserText(
          (summary['confidence_message'] ?? 'AI 신뢰도는 참고 지표이며 실제 상태와 다를 수 있습니다.')
              .toString()),
      severityLabel:
          _cleanUserText((summary['severity_label'] ?? '주의 단계').toString()),
      sourceNote: _cleanUserText((summary['source_note'] ?? '').toString()),
      sources: _sourceList(
        json['sources'] ??
            summary['sources'] ??
            json['references'] ??
            summary['references'] ??
            json['rag_sources'] ??
            summary['rag_sources'] ??
            json['source_url'] ??
            summary['source_url'],
      ),
      hostName: (hostDetection['host_ko'] ?? hostDetection['host'] ?? 'unknown')
          .toString(),
      hostConfidence: (hostDetection['confidence'] ?? 'low').toString(),
      hostReason: (hostDetection['reason'] ?? '').toString(),
      selectionStrategy:
          (json['selection_strategy'] ?? 'raw_classifier').toString(),
    );
  }

  static List<String> _stringList(dynamic value) {
    if (value is! List) return const [];
    final result = <String>[];
    final seen = <String>{};

    for (final raw in value) {
      final cleaned = _cleanUserText(raw.toString());
      if (cleaned.isEmpty) continue;
      final key = _semanticKey(cleaned);
      if (key.isEmpty) continue;

      final duplicate = seen.any((existing) =>
          existing == key ||
          (existing.length >= 12 && key.contains(existing)) ||
          (key.length >= 12 && existing.contains(key)));
      if (!duplicate) {
        seen.add(key);
        result.add(cleaned);
      }
    }
    return List.unmodifiable(result);
  }

  static List<DiagnosisSource> _sourceList(dynamic value) {
    final result = <DiagnosisSource>[];
    final seen = <String>{};

    void add(String title, String url) {
      final normalizedUrl = url.trim();
      if (normalizedUrl.isEmpty) return;
      final cleanTitle = _cleanUserText(title).trim();
      final key = _canonicalSourceKey(cleanTitle, normalizedUrl);
      if (key.isEmpty || !seen.add(key)) return;
      result.add(DiagnosisSource(
        title: cleanTitle.isEmpty ? '참고 출처' : cleanTitle,
        url: normalizedUrl,
      ));
    }

    if (value is String) {
      add('참고 출처', value);
    } else if (value is Map) {
      add(
        (value['title'] ?? value['name'] ?? value['source'] ?? '참고 출처')
            .toString(),
        (value['url'] ?? value['link'] ?? value['source_url'] ?? '').toString(),
      );
    } else if (value is List) {
      for (final item in value) {
        if (item is String) {
          add('참고 출처', item);
        } else if (item is Map) {
          add(
            (item['title'] ?? item['name'] ?? item['source'] ?? '참고 출처')
                .toString(),
            (item['url'] ?? item['link'] ?? item['source_url'] ?? '')
                .toString(),
          );
        }
      }
    }
    return List.unmodifiable(result);
  }

  static double? _firstNumber(Map<String, dynamic> json, List<String> paths) {
    for (final path in paths) {
      dynamic current = json;
      for (final part in path.split('.')) {
        if (current is Map && current.containsKey(part)) {
          current = current[part];
        } else {
          current = null;
          break;
        }
      }
      if (current is num) return current.toDouble();
      if (current is String) {
        final parsed = double.tryParse(current);
        if (parsed != null) return parsed;
      }
    }
    return null;
  }

  static String _cleanUserText(String value) {
    return cleanUnicodeText(value);
  }

  static String _semanticKey(String value) {
    return unicodeSemanticKey(value);
  }

  static String _canonicalSourceKey(String title, String url) {
    final uri = Uri.tryParse(url.trim());
    if (uri == null) {
      return '${_semanticKey(title)}|${url.trim().toLowerCase()}';
    }
    var path = uri.path.replaceAll(RegExp(r'/+$'), '').toLowerCase();
    // 같은 기관의 동일 페이지는 검색어 쿼리가 달라도 출처 한 건으로 묶는다.
    return '${uri.host.toLowerCase()}|$path|${_semanticKey(title)}';
  }

  static String _humanizeDiseaseLabel(String value) {
    final cleaned = value
        .replaceAll(RegExp(r'[_-]+'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    if (cleaned.isEmpty) return '알 수 없음';
    return cleaned
        .split(' ')
        .map((part) =>
            part.isEmpty ? part : part[0].toUpperCase() + part.substring(1))
        .join(' ');
  }
}

class LiveSegmentationService {
  static const MethodChannel _imageConverter =
      MethodChannel('plant_doctor/image_converter');

  LiveSegmentationService({
    required this.serverBaseUrl,
    this.minimumFrameInterval = const Duration(milliseconds: 380),
    this.jpegQuality = 66,
  });

  final String serverBaseUrl;
  final Duration minimumFrameInterval;
  final int jpegQuality;

  bool _busy = false;
  bool _disposed = false;
  DateTime _lastSentAt = DateTime.fromMillisecondsSinceEpoch(0);

  Future<LiveSegmentationResult?> process(
    CameraImage frame, {
    required int rotationDegrees,
  }) async {
    if (_disposed || _busy) return null;

    final now = DateTime.now();
    if (now.difference(_lastSentAt) < minimumFrameInterval) return null;

    _busy = true;
    _lastSentAt = now;
    final stopwatch = Stopwatch()..start();

    try {
      final jpegBytes = cameraImageToJpeg(
        frame,
        rotationDegrees: rotationDegrees,
      );

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$serverBaseUrl/v1/segment'),
      );
      request.headers['ngrok-skip-browser-warning'] = 'true';

      request.files.add(
        http.MultipartFile.fromBytes(
          'image',
          jpegBytes,
          filename: 'camera_frame.jpg',
        ),
      );

      final response = await request.send().timeout(
            const Duration(seconds: 15),
          );
      final responseBytes = await response.stream.toBytes();

      if (response.statusCode != 200) {
        throw Exception(
          '분석 서버 응답 오류 (HTTP ${response.statusCode})',
        );
      }

      final headerRatio = double.tryParse(
        response.headers['x-mask-ratio'] ?? '',
      );
      final maskRatio = headerRatio ?? _calculateMaskRatio(responseBytes);

      stopwatch.stop();
      return LiveSegmentationResult(
        maskPng: Uint8List.fromList(responseBytes),
        frameJpeg: jpegBytes,
        elapsed: stopwatch.elapsed,
        maskRatio: maskRatio,
      );
    } on TimeoutException {
      throw Exception('분석 서버 응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.');
    } on SocketException {
      throw Exception(
        '분석 서버에 연결할 수 없어요.\n'
        'PC에서 Plant Doctor 서버와 ngrok 터널이 실행 중인지 확인해주세요.',
      );
    } on http.ClientException {
      throw Exception(
        '분석 서버 연결이 끊어졌어요.\n'
        'PC 서버와 무선 Funnel 연결 상태를 다시 확인해주세요.',
      );
    } finally {
      _busy = false;
    }
  }

  Future<DiagnosisResult> diagnose(
    XFile photo, {
    required String selectedHostId,
    required String selectedHostKo,
    required String locale,
  }) async {
    final sourceBytes = await photo.readAsBytes();
    if (sourceBytes.isEmpty) {
      throw Exception('촬영된 이미지가 비어 있어요. 다시 촬영해주세요.');
    }

    final jpegBytes = await _normalizeDiagnosisImage(photo.path, sourceBytes);

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$serverBaseUrl/v1/diagnose'),
    );
    request.headers['ngrok-skip-browser-warning'] = 'true';

    request.fields['host'] = selectedHostId;
    request.fields['host_ko'] = selectedHostKo;
    request.fields['locale'] = locale;

    request.files.add(http.MultipartFile.fromBytes(
      'image',
      jpegBytes,
      filename: 'captured_leaf.jpg',
    ));

    try {
      final response = await request.send().timeout(
            const Duration(seconds: 120),
          );
      final responseBytes = await response.stream.toBytes();

      if (response.statusCode != 200) {
        throw Exception(
          '진단 서버 응답 오류 (HTTP ${response.statusCode})\n'
          '${utf8.decode(responseBytes, allowMalformed: true)}',
        );
      }

      return DiagnosisResult.fromJson(
        jsonDecode(utf8.decode(responseBytes)) as Map<String, dynamic>,
      );
    } on TimeoutException {
      throw Exception('AI 진단 시간이 오래 걸리고 있어요. 잠시 후 다시 시도해주세요.');
    } on SocketException {
      throw Exception(
        '진단 서버에 연결할 수 없어요.\n'
        'PC에서 FastAPI 서버가 실행 중인지 확인해주세요.',
      );
    } on http.ClientException {
      throw Exception(
        '진단 서버 연결이 끊어졌어요.\n'
        'PC 서버와 ngrok 터널 상태를 다시 확인해주세요.',
      );
    }
  }

  Future<Uint8List> _normalizeDiagnosisImage(
    String path,
    Uint8List sourceBytes,
  ) async {
    final decoded = img.decodeImage(sourceBytes);
    if (decoded != null) {
      final normalized = img.bakeOrientation(decoded);
      return Uint8List.fromList(img.encodeJpg(normalized, quality: 92));
    }

    try {
      final converted = await _imageConverter.invokeMethod<Uint8List>(
        'convertToJpeg',
        <String, Object>{
          'path': path,
          'quality': 92,
          'maxDimension': 2400,
        },
      );
      if (converted != null && converted.isNotEmpty) {
        return converted;
      }
    } on PlatformException {
      // Some Android devices do not ship codecs for every HEIC/HEIF/AVIF
      // container. Send the untouched bytes so the server-side codec can
      // decode and normalize them instead.
      return sourceBytes;
    } on MissingPluginException {
      return sourceBytes;
    }

    return sourceBytes;
  }

  Uint8List cameraImageToJpeg(
    CameraImage frame, {
    required int rotationDegrees,
  }) {
    final img.Image rgbImage;

    switch (frame.format.group) {
      case ImageFormatGroup.yuv420:
        rgbImage = _convertYuv420(frame);
        break;
      case ImageFormatGroup.bgra8888:
        rgbImage = _convertBgra8888(frame);
        break;
      default:
        throw UnsupportedError(
          '지원하지 않는 카메라 형식: ${frame.format.group}',
        );
    }

    final normalizedRotation = rotationDegrees % 360;
    final rotated = normalizedRotation == 0
        ? rgbImage
        : img.copyRotate(
            rgbImage,
            angle: normalizedRotation,
          );

    return Uint8List.fromList(
      img.encodeJpg(
        rotated,
        quality: jpegQuality,
      ),
    );
  }

  double _calculateMaskRatio(Uint8List pngBytes) {
    final decoded = img.decodePng(pngBytes);
    if (decoded == null || decoded.width == 0 || decoded.height == 0) {
      return 0;
    }

    var active = 0;
    final total = decoded.width * decoded.height;

    for (final pixel in decoded) {
      if (pixel.r > 127) {
        active++;
      }
    }

    return active / total;
  }

  img.Image _convertBgra8888(CameraImage frame) {
    final plane = frame.planes.first;
    return img.Image.fromBytes(
      width: frame.width,
      height: frame.height,
      bytes: plane.bytes.buffer,
      rowStride: plane.bytesPerRow,
      order: img.ChannelOrder.bgra,
    );
  }

  img.Image _convertYuv420(CameraImage frame) {
    final width = frame.width;
    final height = frame.height;
    final output = img.Image(width: width, height: height);

    final yPlane = frame.planes[0];
    final uPlane = frame.planes[1];
    final vPlane = frame.planes[2];
    final uvPixelStride = uPlane.bytesPerPixel ?? 1;

    for (var y = 0; y < height; y++) {
      final uvRow = y >> 1;

      for (var x = 0; x < width; x++) {
        final uvColumn = x >> 1;
        final yIndex = y * yPlane.bytesPerRow + x;
        final uvIndex = uvRow * uPlane.bytesPerRow + uvColumn * uvPixelStride;

        final yValue = yPlane.bytes[yIndex];
        final uValue = uPlane.bytes[uvIndex];
        final vValue = vPlane.bytes[uvIndex];

        final red = (yValue + 1.402 * (vValue - 128)).round().clamp(0, 255);
        final green =
            (yValue - 0.344136 * (uValue - 128) - 0.714136 * (vValue - 128))
                .round()
                .clamp(0, 255);
        final blue = (yValue + 1.772 * (uValue - 128)).round().clamp(0, 255);

        output.setPixelRgba(x, y, red, green, blue, 255);
      }
    }

    return output;
  }

  void dispose() {
    _disposed = true;
  }
}
