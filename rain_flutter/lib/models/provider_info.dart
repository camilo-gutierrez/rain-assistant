enum AIProvider { claude, openai, gemini }

class ProviderModelInfo {
  final String id;
  final String name;
  const ProviderModelInfo(this.id, this.name);
}

const providerModels = <AIProvider, List<ProviderModelInfo>>{
  AIProvider.claude: [
    ProviderModelInfo('auto', 'Auto (SDK)'),
  ],
  AIProvider.openai: [
    ProviderModelInfo('gpt-4o', 'GPT-4o'),
    ProviderModelInfo('gpt-4o-mini', 'GPT-4o Mini'),
    ProviderModelInfo('gpt-4.1', 'GPT-4.1'),
    ProviderModelInfo('gpt-4.1-mini', 'GPT-4.1 Mini'),
    ProviderModelInfo('gpt-4.1-nano', 'GPT-4.1 Nano'),
    ProviderModelInfo('o3-mini', 'o3-mini'),
    ProviderModelInfo('o4-mini', 'o4-mini'),
  ],
  AIProvider.gemini: [
    ProviderModelInfo('gemini-2.5-pro', 'Gemini 2.5 Pro'),
    ProviderModelInfo('gemini-2.5-flash', 'Gemini 2.5 Flash'),
    ProviderModelInfo('gemini-2.0-flash', 'Gemini 2.0 Flash'),
    ProviderModelInfo('gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite'),
  ],
};

const providerInfo = <AIProvider, ProviderDisplay>{
  AIProvider.claude: ProviderDisplay(
    name: 'Claude',
    keyPlaceholder: 'sk-ant-...',
    consoleUrl: 'https://console.anthropic.com',
  ),
  AIProvider.openai: ProviderDisplay(
    name: 'OpenAI',
    keyPlaceholder: 'sk-...',
    consoleUrl: 'https://platform.openai.com/api-keys',
  ),
  AIProvider.gemini: ProviderDisplay(
    name: 'Gemini',
    keyPlaceholder: 'AIza...',
    consoleUrl: 'https://aistudio.google.com/apikey',
  ),
};

class ProviderDisplay {
  final String name;
  final String keyPlaceholder;
  final String consoleUrl;
  const ProviderDisplay({
    required this.name,
    required this.keyPlaceholder,
    required this.consoleUrl,
  });
}

const modelShortNames = <String, String>{
  'claude-sonnet-4-5-20250929': 'Sonnet 4.5',
  'claude-sonnet-4-20250514': 'Sonnet 4',
  'claude-opus-4-20250514': 'Opus 4',
  'claude-opus-4-6': 'Opus 4.6',
  'claude-haiku-3-5-20241022': 'Haiku 3.5',
  'claude-3-5-sonnet-20241022': 'Sonnet 3.5',
};

String formatModelName(String raw) {
  if (modelShortNames.containsKey(raw)) return modelShortNames[raw]!;
  for (final entry in modelShortNames.entries) {
    final prefix = entry.key.replaceAll(RegExp(r'-\d{8}$'), '');
    if (raw.startsWith(prefix)) return entry.value;
  }
  return raw.length > 24 ? '${raw.substring(0, 22)}...' : raw;
}
