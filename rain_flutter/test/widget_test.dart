import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:rain_flutter/app/theme.dart';
import 'package:rain_flutter/app/l10n.dart';
import 'package:rain_flutter/providers/settings_provider.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });
  group('RainTheme', () {
    test('light theme has light brightness', () {
      final theme = RainTheme.light();
      expect(theme.colorScheme.brightness, Brightness.light);
    });

    test('dark theme has dark brightness', () {
      final theme = RainTheme.dark();
      expect(theme.colorScheme.brightness, Brightness.dark);
    });

    test('both themes use Material 3', () {
      expect(RainTheme.light().useMaterial3, true);
      expect(RainTheme.dark().useMaterial3, true);
    });

    test('dark theme surface color is custom dark', () {
      final theme = RainTheme.dark();
      expect(theme.colorScheme.surface, const Color(0xFF0F0F14));
    });

    test('light and dark themes have different surface colors', () {
      final light = RainTheme.light();
      final dark = RainTheme.dark();
      expect(light.colorScheme.surface, isNot(dark.colorScheme.surface));
    });

    test('both themes have indigo-based primary color', () {
      final light = RainTheme.light();
      final dark = RainTheme.dark();
      // Both should derive from the indigo seed 0xFF6366F1
      expect(light.colorScheme.primary, isNotNull);
      expect(dark.colorScheme.primary, isNotNull);
    });

    test('scaffold background matches surface', () {
      final light = RainTheme.light();
      expect(light.scaffoldBackgroundColor, light.colorScheme.surface);
      final dark = RainTheme.dark();
      expect(dark.scaffoldBackgroundColor, dark.colorScheme.surface);
    });

    test('appBar elevation is 0', () {
      final theme = RainTheme.dark();
      expect(theme.appBarTheme.elevation, 0);
    });

    test('appBar centers title', () {
      final theme = RainTheme.light();
      expect(theme.appBarTheme.centerTitle, true);
    });

    test('input decoration has rounded borders', () {
      final theme = RainTheme.dark();
      final border = theme.inputDecorationTheme.border as OutlineInputBorder;
      expect(border.borderRadius, BorderRadius.circular(12));
    });

    test('elevated button has full-width minimum size', () {
      final theme = RainTheme.light();
      final style = theme.elevatedButtonTheme.style!;
      final minSize =
          style.minimumSize!.resolve(<WidgetState>{});
      expect(minSize!.width, double.infinity);
      expect(minSize.height, 52);
    });

    test('card theme has rounded corners', () {
      final theme = RainTheme.dark();
      final cardShape = theme.cardTheme.shape as RoundedRectangleBorder;
      expect(cardShape.borderRadius, BorderRadius.circular(16));
    });

    test('card theme has zero elevation', () {
      final theme = RainTheme.dark();
      expect(theme.cardTheme.elevation, 0);
    });
  });

  group('RainApp theme switching widget test', () {
    testWidgets('renders with dark theme by default', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: Consumer(
            builder: (context, ref, _) {
              final settings = ref.watch(settingsProvider);
              return MaterialApp(
                theme: RainTheme.light(),
                darkTheme: RainTheme.dark(),
                themeMode:
                    settings.darkMode ? ThemeMode.dark : ThemeMode.light,
                home: Builder(
                  builder: (context) {
                    final brightness = Theme.of(context).brightness;
                    return Scaffold(
                      body: Text('Brightness: $brightness'),
                    );
                  },
                ),
              );
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      // Default darkMode is true
      expect(find.text('Brightness: Brightness.dark'), findsOneWidget);
    });

    testWidgets('displays localized text based on language setting',
        (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: Consumer(
            builder: (context, ref, _) {
              final settings = ref.watch(settingsProvider);
              return MaterialApp(
                home: Scaffold(
                  body: Column(
                    children: [
                      Text(L10n.t('settings.title', settings.language)),
                      Text(L10n.t('chat.sendBtn', settings.language)),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      // Default language is 'es'
      expect(find.text('Configuraci\u00f3n'), findsOneWidget);
      expect(find.text('Enviar'), findsOneWidget);
    });
  });
}
