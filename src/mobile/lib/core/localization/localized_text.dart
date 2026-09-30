import 'dart:convert';

import 'package:flutter/material.dart' as material;
import 'package:flutter/widgets.dart';
import 'package:flutter/services.dart';

class AppTranslationController extends ChangeNotifier
    with WidgetsBindingObserver {
  AppTranslationController._() {
    WidgetsBinding.instance.addObserver(this);
  }

  static final AppTranslationController instance = AppTranslationController._();
  final Map<String, String> _translated = {};
  final List<_TranslationTemplate> _templates = [];
  String _locale =
      WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag();

  Future<void> initialize() => _loadLocale(_locale);

  String translate(String source) {
    if (_locale.toLowerCase().startsWith('ko') ||
        !RegExp(r'[가-힣]').hasMatch(source)) {
      return source;
    }
    final exact =
        _translated[source] ?? _translated[source.replaceAll('\n', r'\n')];
    if (exact != null) return exact.replaceAll(r'\n', '\n');
    for (final template in _templates) {
      final translated = template.translate(source, translate);
      if (translated != null) return translated;
    }
    // Never translate arbitrary fragments inside server/LLM output. Partial
    // replacement creates mixed strings such as "Disease 항목입니다".
    return source;
  }

  @override
  void didChangeLocales(List<Locale>? locales) {
    final next = (locales?.isNotEmpty ?? false)
        ? locales!.first.toLanguageTag()
        : WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag();
    if (next == _locale) return;
    _locale = next;
    _loadLocale(next);
  }

  Future<void> _loadLocale(String locale) async {
    final language = locale.split(RegExp('[-_]')).first.toLowerCase();
    Map<String, String> loaded = {};
    try {
      final raw = await rootBundle.loadString('assets/i18n/$language.json');
      final decoded = jsonDecode(raw);
      if (decoded is Map) {
        loaded = decoded.map(
          (key, value) => MapEntry(key.toString(), value.toString()),
        );
      }
    } catch (_) {
      try {
        final raw = await rootBundle.loadString('assets/i18n/ko.json');
        final decoded = jsonDecode(raw);
        if (decoded is Map) {
          loaded = decoded.map(
            (key, value) => MapEntry(key.toString(), value.toString()),
          );
        }
      } catch (_) {
        loaded = {};
      }
    }
    if (_locale != locale) return;
    _translated
      ..clear()
      ..addAll(loaded);
    _templates
      ..clear()
      ..addAll(
        loaded.entries
            .where((entry) => _TranslationTemplate.hasPlaceholder(entry.key))
            .map(_TranslationTemplate.fromEntry),
      );
    notifyListeners();
  }
}

class _TranslationTemplate {
  _TranslationTemplate(this.pattern, this.placeholders, this.translation);

  static final RegExp _placeholder =
      RegExp(r'\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*');

  final RegExp pattern;
  final List<String> placeholders;
  final String translation;

  static bool hasPlaceholder(String value) => _placeholder.hasMatch(value);

  factory _TranslationTemplate.fromEntry(MapEntry<String, String> entry) {
    final placeholders = _placeholder
        .allMatches(entry.key)
        .map((match) => match.group(0)!)
        .toList();
    final patternText = StringBuffer('^');
    var cursor = 0;
    for (final match in _placeholder.allMatches(entry.key)) {
      patternText
          .write(RegExp.escape(entry.key.substring(cursor, match.start)));
      patternText.write('(.*?)');
      cursor = match.end;
    }
    patternText.write(RegExp.escape(entry.key.substring(cursor)));
    patternText.write(r'$');
    return _TranslationTemplate(
      RegExp(patternText.toString(), dotAll: true),
      placeholders,
      entry.value,
    );
  }

  String? translate(String source, String Function(String) translateValue) {
    final match = pattern.firstMatch(source);
    if (match == null) return null;
    var result = translation;
    for (var index = 0; index < placeholders.length; index++) {
      result = result.replaceFirst(
        placeholders[index],
        translateValue(match.group(index + 1) ?? ''),
      );
    }
    return result;
  }
}

class Text extends StatelessWidget {
  const Text(
    this.data, {
    super.key,
    this.style,
    this.strutStyle,
    this.textAlign,
    this.textDirection,
    this.locale,
    this.softWrap,
    this.overflow,
    this.textScaler,
    this.maxLines,
    this.semanticsLabel,
    this.textWidthBasis,
    this.textHeightBehavior,
    this.selectionColor,
  });

  final String data;
  final TextStyle? style;
  final StrutStyle? strutStyle;
  final TextAlign? textAlign;
  final TextDirection? textDirection;
  final Locale? locale;
  final bool? softWrap;
  final TextOverflow? overflow;
  final TextScaler? textScaler;
  final int? maxLines;
  final String? semanticsLabel;
  final TextWidthBasis? textWidthBasis;
  final TextHeightBehavior? textHeightBehavior;
  final Color? selectionColor;

  @override
  Widget build(BuildContext context) {
    final controller = AppTranslationController.instance;
    return AnimatedBuilder(
      animation: controller,
      builder: (_, __) => material.Text(
        controller.translate(data),
        style: style,
        strutStyle: strutStyle,
        textAlign: textAlign,
        textDirection: textDirection,
        locale: locale,
        softWrap: softWrap,
        overflow: overflow,
        textScaler: textScaler,
        maxLines: maxLines,
        semanticsLabel: semanticsLabel,
        textWidthBasis: textWidthBasis,
        textHeightBehavior: textHeightBehavior,
        selectionColor: selectionColor,
      ),
    );
  }
}
