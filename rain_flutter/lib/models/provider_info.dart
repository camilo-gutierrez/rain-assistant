enum AIProvider { claude, openai, gemini, ollama }

class ProviderModelInfo {
  final String id;
  final String name;
  const ProviderModelInfo(this.id, this.name);
}

const providerModels = <AIProvider, List<ProviderModelInfo>>{
  AIProvider.claude: [
    ProviderModelInfo('auto', 'Auto (SDK)'),
    ProviderModelInfo('claude-opus-4-6', 'Opus 4.6'),
    ProviderModelInfo('claude-sonnet-4-6', 'Sonnet 4.6'),
    ProviderModelInfo('claude-haiku-4-5-20251001', 'Haiku 4.5'),
    ProviderModelInfo('claude-sonnet-4-5-20250929', 'Sonnet 4.5'),
  ],
  AIProvider.openai: [
    ProviderModelInfo('gpt-5.2', 'GPT-5.2'),
    ProviderModelInfo('gpt-5.1', 'GPT-5.1'),
    ProviderModelInfo('gpt-5', 'GPT-5'),
    ProviderModelInfo('gpt-5-mini', 'GPT-5 Mini'),
    ProviderModelInfo('gpt-5-nano', 'GPT-5 Nano'),
    ProviderModelInfo('o3', 'o3'),
    ProviderModelInfo('o3-mini', 'o3-mini'),
    ProviderModelInfo('o4-mini', 'o4-mini'),
    ProviderModelInfo('gpt-4o', 'GPT-4o'),
    ProviderModelInfo('gpt-4o-mini', 'GPT-4o Mini'),
  ],
  AIProvider.gemini: [
    ProviderModelInfo('gemini-3.1-pro-preview', 'Gemini 3.1 Pro'),
    ProviderModelInfo('gemini-3-pro-preview', 'Gemini 3 Pro'),
    ProviderModelInfo('gemini-3-flash-preview', 'Gemini 3 Flash'),
    ProviderModelInfo('gemini-2.5-pro', 'Gemini 2.5 Pro'),
    ProviderModelInfo('gemini-2.5-flash', 'Gemini 2.5 Flash'),
    ProviderModelInfo('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite'),
  ],
  AIProvider.ollama: [
    ProviderModelInfo('llama3.3', 'Llama 3.3'),
    ProviderModelInfo('qwen2.5-coder', 'Qwen 2.5 Coder'),
    ProviderModelInfo('deepseek-r1', 'DeepSeek R1'),
    ProviderModelInfo('mistral', 'Mistral'),
    ProviderModelInfo('gemma2', 'Gemma 2'),
    ProviderModelInfo('phi4', 'Phi 4'),
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
  AIProvider.ollama: ProviderDisplay(
    name: 'Ollama',
    keyPlaceholder: 'not-needed',
    consoleUrl: 'https://ollama.com',
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
  'claude-opus-4-6': 'Opus 4.6',
  'claude-sonnet-4-6': 'Sonnet 4.6',
  'claude-haiku-4-5-20251001': 'Haiku 4.5',
  'claude-sonnet-4-5-20250929': 'Sonnet 4.5',
  'claude-opus-4-5-20251101': 'Opus 4.5',
  'claude-opus-4-1-20250805': 'Opus 4.1',
  'claude-sonnet-4-20250514': 'Sonnet 4',
  'claude-opus-4-20250514': 'Opus 4',
};

String formatModelName(String raw) {
  if (modelShortNames.containsKey(raw)) return modelShortNames[raw]!;
  for (final entry in modelShortNames.entries) {
    final prefix = entry.key.replaceAll(RegExp(r'-\d{8}$'), '');
    if (raw.startsWith(prefix)) return entry.value;
  }
  return raw.length > 24 ? '${raw.substring(0, 22)}...' : raw;
}
