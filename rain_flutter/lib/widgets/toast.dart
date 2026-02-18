import 'package:flutter/material.dart';

enum ToastType { info, success, error, warning }

/// Show a brief toast-like notification at the bottom of the screen.
void showToast(
  BuildContext context,
  String message, {
  ToastType type = ToastType.info,
  Duration duration = const Duration(seconds: 3),
}) {
  final cs = Theme.of(context).colorScheme;
  final (Color bg, Color fg, IconData icon) = switch (type) {
    ToastType.success => (Colors.green.shade800, Colors.white, Icons.check_circle),
    ToastType.error => (cs.error, cs.onError, Icons.error_outline),
    ToastType.warning => (Colors.orange.shade800, Colors.white, Icons.warning_amber),
    ToastType.info => (cs.inverseSurface, cs.onInverseSurface, Icons.info_outline),
  };

  ScaffoldMessenger.of(context).clearSnackBars();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Row(
        children: [
          Icon(icon, color: fg, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message, style: TextStyle(color: fg, fontSize: 13)),
          ),
        ],
      ),
      backgroundColor: bg,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      duration: duration,
      dismissDirection: DismissDirection.horizontal,
    ),
  );
}
