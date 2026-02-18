import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/rate_limits.dart';

/// Rate limits from the server (via WebSocket).
final rateLimitsProvider = StateProvider<RateLimits>((ref) => const RateLimits());

/// Current model ID from the server (via model_info WS message).
final currentModelProvider = StateProvider<String>((ref) => '');
