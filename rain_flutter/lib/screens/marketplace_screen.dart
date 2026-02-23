import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/l10n.dart';
import '../providers/connection_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/toast.dart';

class MarketplaceScreen extends ConsumerStatefulWidget {
  const MarketplaceScreen({super.key});

  @override
  ConsumerState<MarketplaceScreen> createState() => _MarketplaceScreenState();
}

class _MarketplaceScreenState extends ConsumerState<MarketplaceScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  // ── Browse tab state ──
  final TextEditingController _searchController = TextEditingController();
  List<Map<String, dynamic>> _skills = [];
  List<Map<String, dynamic>> _categories = [];
  String? _selectedCategory;
  bool _browseLoading = true;
  String? _browseError;
  int _page = 1;
  final Set<String> _installingNames = {};

  // ── Installed tab state ──
  List<Map<String, dynamic>> _installed = [];
  bool _installedLoading = true;
  String? _installedError;
  String? _confirmUninstallName;
  final Set<String> _uninstallingNames = {};

  // ── Updates tab state ──
  List<Map<String, dynamic>> _updates = [];
  bool _updatesLoading = true;
  String? _updatesError;
  final Set<String> _updatingNames = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadCategories();
    _loadSkills();
    _loadInstalled();
    _loadUpdates();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    switch (_tabController.index) {
      case 1:
        _loadInstalled();
        break;
      case 2:
        _loadUpdates();
        break;
    }
  }

  // ── API helpers ──

  Future<void> _loadCategories() async {
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/marketplace/categories');
      if (!mounted) return;
      final list = (res.data['categories'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      setState(() => _categories = list);
    } catch (_) {
      // Categories are non-critical; silently ignore errors.
    }
  }

  Future<void> _loadSkills() async {
    setState(() {
      _browseLoading = true;
      _browseError = null;
    });
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final query = <String, dynamic>{'page': _page};
      final search = _searchController.text.trim();
      if (search.isNotEmpty) query['q'] = search;
      if (_selectedCategory != null) query['category'] = _selectedCategory;
      final res =
          await dio.get('/marketplace/skills', queryParameters: query);
      if (!mounted) return;
      setState(() {
        _skills = (res.data['skills'] as List? ?? [])
            .cast<Map<String, dynamic>>();
        _browseLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _browseError = e.toString();
        _browseLoading = false;
      });
    }
  }

  Future<void> _loadInstalled() async {
    setState(() {
      _installedLoading = true;
      _installedError = null;
    });
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/marketplace/installed');
      if (!mounted) return;
      setState(() {
        _installed = (res.data['skills'] as List? ?? [])
            .cast<Map<String, dynamic>>();
        _installedLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _installedError = e.toString();
        _installedLoading = false;
      });
    }
  }

  Future<void> _loadUpdates() async {
    setState(() {
      _updatesLoading = true;
      _updatesError = null;
    });
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.get('/marketplace/updates');
      if (!mounted) return;
      setState(() {
        _updates = (res.data['updates'] as List? ?? [])
            .cast<Map<String, dynamic>>();
        _updatesLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _updatesError = e.toString();
        _updatesLoading = false;
      });
    }
  }

  Future<void> _installSkill(String name) async {
    final lang = ref.read(settingsProvider).language;
    setState(() => _installingNames.add(name));
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      final res = await dio.post('/marketplace/install/$name');
      if (!mounted) return;
      final requiresEnv =
          (res.data['requires_env'] as List?)?.cast<String>() ?? [];
      if (requiresEnv.isNotEmpty) {
        showToast(
          context,
          '${L10n.t('market.requiresEnv', lang)}: ${requiresEnv.join(', ')}',
          type: ToastType.warning,
        );
      } else {
        showToast(context, '${L10n.t('market.install', lang)}: $name',
            type: ToastType.success);
      }
      _loadInstalled();
      _loadUpdates();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    } finally {
      if (mounted) setState(() => _installingNames.remove(name));
    }
  }

  Future<void> _uninstallSkill(String name) async {
    final lang = ref.read(settingsProvider).language;
    setState(() => _uninstallingNames.add(name));
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.delete('/marketplace/install/$name');
      if (!mounted) return;
      showToast(context, '${L10n.t('market.uninstall', lang)}: $name',
          type: ToastType.info);
      _loadInstalled();
      _loadUpdates();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    } finally {
      if (mounted) {
        setState(() {
          _uninstallingNames.remove(name);
          _confirmUninstallName = null;
        });
      }
    }
  }

  Future<void> _updateSkill(String name) async {
    final lang = ref.read(settingsProvider).language;
    setState(() => _updatingNames.add(name));
    try {
      final dio = ref.read(authServiceProvider).authenticatedDio;
      await dio.post('/marketplace/update/$name');
      if (!mounted) return;
      showToast(context, '${L10n.t('market.update', lang)}: $name',
          type: ToastType.success);
      _loadUpdates();
      _loadInstalled();
    } catch (e) {
      if (!mounted) return;
      showToast(context, e.toString(), type: ToastType.error);
    } finally {
      if (mounted) setState(() => _updatingNames.remove(name));
    }
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lang = ref.watch(settingsProvider).language;

    return Scaffold(
      appBar: AppBar(
        title: Text(L10n.t('market.title', lang)),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: L10n.t('market.browse', lang)),
            Tab(text: L10n.t('market.installed', lang)),
            Tab(text: L10n.t('market.updates', lang)),
          ],
        ),
        actions: [
          IconButton(
            onPressed: () {
              switch (_tabController.index) {
                case 0:
                  _loadSkills();
                  break;
                case 1:
                  _loadInstalled();
                  break;
                case 2:
                  _loadUpdates();
                  break;
              }
            },
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildBrowseTab(cs, lang),
          _buildInstalledTab(cs, lang),
          _buildUpdatesTab(cs, lang),
        ],
      ),
    );
  }

  // ── Browse tab ──

  Widget _buildBrowseTab(ColorScheme cs, String lang) {
    return Column(
      children: [
        // Search bar
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: L10n.t('market.search', lang),
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        _page = 1;
                        _loadSkills();
                      },
                    )
                  : null,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            ),
            onSubmitted: (_) {
              _page = 1;
              _loadSkills();
            },
          ),
        ),

        // Category chips
        if (_categories.isNotEmpty)
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: FilterChip(
                    label: Text(L10n.t('market.allCategories', lang)),
                    selected: _selectedCategory == null,
                    onSelected: (_) {
                      setState(() => _selectedCategory = null);
                      _page = 1;
                      _loadSkills();
                    },
                  ),
                ),
                ..._categories.map((cat) {
                  final id = cat['id'] as String? ?? '';
                  final name = cat['name'] as String? ?? id;
                  final count = cat['count'] as int? ?? 0;
                  return Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: FilterChip(
                      label: Text('$name ($count)'),
                      selected: _selectedCategory == id,
                      onSelected: (_) {
                        setState(() {
                          _selectedCategory =
                              _selectedCategory == id ? null : id;
                        });
                        _page = 1;
                        _loadSkills();
                      },
                    ),
                  );
                }),
              ],
            ),
          ),

        // Skill list
        Expanded(
          child: _browseLoading
              ? const Center(child: CircularProgressIndicator())
              : _browseError != null
                  ? _buildErrorState(cs, lang, _browseError!, _loadSkills)
                  : _skills.isEmpty
                      ? _buildEmptyState(
                          cs, lang, Icons.search_off, 'market.noResults')
                      : ListView.builder(
                          padding: const EdgeInsets.only(
                              left: 16, right: 16, top: 4, bottom: 16),
                          itemCount: _skills.length,
                          itemBuilder: (context, index) {
                            return _SkillCard(
                              skill: _skills[index],
                              lang: lang,
                              installing: _installingNames
                                  .contains(_skills[index]['name']),
                              onInstall: () =>
                                  _installSkill(_skills[index]['name'] as String),
                            );
                          },
                        ),
        ),
      ],
    );
  }

  // ── Installed tab ──

  Widget _buildInstalledTab(ColorScheme cs, String lang) {
    if (_installedLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_installedError != null) {
      return _buildErrorState(cs, lang, _installedError!, _loadInstalled);
    }
    if (_installed.isEmpty) {
      return _buildEmptyState(
          cs, lang, Icons.inventory_2_outlined, 'market.empty');
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _installed.length,
      itemBuilder: (context, index) {
        final skill = _installed[index];
        final name = skill['name'] as String? ?? '';
        final displayName = skill['display_name'] as String? ?? name;
        final version = skill['version'] as String? ?? '';
        final installedAt = skill['installed_at'] as String? ?? '';
        final isConfirming = _confirmUninstallName == name;
        final isUninstalling = _uninstallingNames.contains(name);

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            title: Text(
              displayName,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              'v$version${installedAt.isNotEmpty ? '  |  $installedAt' : ''}',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
            trailing: isUninstalling
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : isConfirming
                    ? Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          TextButton(
                            onPressed: () =>
                                setState(() => _confirmUninstallName = null),
                            child: Text(L10n.t('agent.cancel', lang)),
                          ),
                          const SizedBox(width: 4),
                          FilledButton(
                            style: FilledButton.styleFrom(
                              backgroundColor: cs.error,
                              foregroundColor: cs.onError,
                            ),
                            onPressed: () => _uninstallSkill(name),
                            child: Text(L10n.t('market.uninstall', lang)),
                          ),
                        ],
                      )
                    : TextButton(
                        onPressed: () =>
                            setState(() => _confirmUninstallName = name),
                        style: TextButton.styleFrom(
                          foregroundColor: cs.error,
                        ),
                        child: Text(L10n.t('market.uninstall', lang)),
                      ),
          ),
        );
      },
    );
  }

  // ── Updates tab ──

  Widget _buildUpdatesTab(ColorScheme cs, String lang) {
    if (_updatesLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_updatesError != null) {
      return _buildErrorState(cs, lang, _updatesError!, _loadUpdates);
    }
    if (_updates.isEmpty) {
      return _buildEmptyState(
          cs, lang, Icons.update_disabled, 'market.noUpdates');
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _updates.length,
      itemBuilder: (context, index) {
        final upd = _updates[index];
        final name = upd['name'] as String? ?? '';
        final currentVersion = upd['current_version'] as String? ?? '';
        final latestVersion = upd['latest_version'] as String? ?? '';
        final isUpdating = _updatingNames.contains(name);

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Icon(Icons.upgrade, color: cs.primary),
            title: Text(
              name,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              'v$currentVersion  ->  v$latestVersion',
              style: TextStyle(
                fontSize: 12,
                color: cs.onSurfaceVariant,
                fontFamily: 'monospace',
              ),
            ),
            trailing: isUpdating
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : FilledButton.tonal(
                    onPressed: () => _updateSkill(name),
                    child: Text(L10n.t('market.update', lang)),
                  ),
          ),
        );
      },
    );
  }

  // ── Shared helpers ──

  Widget _buildErrorState(
    ColorScheme cs,
    String lang,
    String error,
    VoidCallback onRetry,
  ) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: cs.error),
            const SizedBox(height: 16),
            Text(
              error,
              style: TextStyle(color: cs.error, fontSize: 13),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton.tonal(
              onPressed: onRetry,
              child: const Icon(Icons.refresh),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(
    ColorScheme cs,
    String lang,
    IconData icon,
    String l10nKey,
  ) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon,
              size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
          const SizedBox(height: 16),
          Text(
            L10n.t(l10nKey, lang),
            style: TextStyle(color: cs.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

// ── Skill card for the Browse tab ──

class _SkillCard extends StatelessWidget {
  final Map<String, dynamic> skill;
  final String lang;
  final bool installing;
  final VoidCallback onInstall;

  const _SkillCard({
    required this.skill,
    required this.lang,
    required this.installing,
    required this.onInstall,
  });

  Color _permissionColor(String? level) {
    switch (level) {
      case 'green':
        return Colors.green;
      case 'yellow':
        return Colors.orange;
      case 'red':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  String _formatDownloads(int count) {
    if (count >= 1000000) return '${(count / 1000000).toStringAsFixed(1)}M';
    if (count >= 1000) return '${(count / 1000).toStringAsFixed(1)}K';
    return '$count';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final name = skill['name'] as String? ?? '';
    final displayName = skill['display_name'] as String? ?? name;
    final description = skill['description'] as String? ?? '';
    final author = skill['author'] as String? ?? '';
    final permissionLevel = skill['permission_level'] as String?;
    final verified = skill['verified'] as bool? ?? false;
    final downloads = skill['downloads'] as int? ?? 0;
    final tags = (skill['tags'] as List?)?.cast<String>() ?? [];

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: name + verified + permission dot
            Row(
              children: [
                // Permission level dot
                Container(
                  width: 10,
                  height: 10,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _permissionColor(permissionLevel),
                  ),
                ),
                Expanded(
                  child: Text(
                    displayName,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 15,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (verified)
                  Tooltip(
                    message: L10n.t('market.verified', lang),
                    child: Icon(
                      Icons.verified,
                      size: 18,
                      color: cs.primary,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),

            // Description
            if (description.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  description,
                  style: TextStyle(
                    fontSize: 13,
                    color: cs.onSurfaceVariant,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),

            // Tags
            if (tags.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  children: tags
                      .map((tag) => Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: cs.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              tag,
                              style: TextStyle(
                                fontSize: 11,
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ))
                      .toList(),
                ),
              ),

            // Footer: author, downloads, install button
            Row(
              children: [
                if (author.isNotEmpty) ...[
                  Icon(Icons.person_outline, size: 14, color: cs.onSurfaceVariant),
                  const SizedBox(width: 4),
                  Text(
                    author,
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                  ),
                  const SizedBox(width: 12),
                ],
                Icon(Icons.download_outlined,
                    size: 14, color: cs.onSurfaceVariant),
                const SizedBox(width: 4),
                Text(
                  _formatDownloads(downloads),
                  style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                ),
                const Spacer(),
                installing
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : FilledButton.tonal(
                        onPressed: onInstall,
                        child: Text(L10n.t('market.install', lang)),
                      ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
