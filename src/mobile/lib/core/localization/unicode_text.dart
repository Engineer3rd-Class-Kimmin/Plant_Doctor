String cleanUnicodeText(String value) {
  return value
      .replaceAll(
        RegExp(r'[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]'),
        '',
      )
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
}

String unicodeSemanticKey(String value) {
  return value
      .replaceAll(
        RegExp(r'''[\s>→▶▷〉、。，．・…:;!?！？（）()\[\]{}"'`~_\-]+'''),
        '',
      )
      .toLowerCase();
}
