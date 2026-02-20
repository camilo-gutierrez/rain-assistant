import 'dart:convert';
import 'package:flutter/material.dart';

/// Fullscreen screenshot viewer with zoom and pan via InteractiveViewer.
class ScreenshotFullscreen extends StatelessWidget {
  final String base64Image;
  final String title;

  const ScreenshotFullscreen({
    super.key,
    required this.base64Image,
    this.title = '',
  });

  static void show(BuildContext context, String base64Image, {String title = ''}) {
    Navigator.of(context).push(
      PageRouteBuilder(
        opaque: false,
        barrierColor: Colors.black87,
        barrierDismissible: true,
        pageBuilder: (_, __, ___) =>
            ScreenshotFullscreen(base64Image: base64Image, title: title),
        transitionsBuilder: (_, animation, __, child) {
          return FadeTransition(opacity: animation, child: child);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final bytes = base64Decode(base64Image);

    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.black54,
        foregroundColor: Colors.white,
        title: title.isNotEmpty
            ? Text(title, style: const TextStyle(fontSize: 14))
            : null,
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: GestureDetector(
        onTap: () => Navigator.of(context).pop(),
        child: InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: Center(
            child: Image.memory(
              bytes,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => Icon(
                Icons.broken_image,
                size: 64,
                color: cs.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
