class RateLimits {
  final int? requestsLimit;
  final int? requestsRemaining;
  final String? requestsReset;
  final int? inputTokensLimit;
  final int? inputTokensRemaining;
  final String? inputTokensReset;
  final int? outputTokensLimit;
  final int? outputTokensRemaining;
  final String? outputTokensReset;

  const RateLimits({
    this.requestsLimit,
    this.requestsRemaining,
    this.requestsReset,
    this.inputTokensLimit,
    this.inputTokensRemaining,
    this.inputTokensReset,
    this.outputTokensLimit,
    this.outputTokensRemaining,
    this.outputTokensReset,
  });

  bool get hasData => requestsLimit != null;

  double get requestsPercent =>
      (requestsLimit != null && requestsLimit! > 0 && requestsRemaining != null)
          ? requestsRemaining! / requestsLimit!
          : 1.0;

  double get inputTokensPercent =>
      (inputTokensLimit != null &&
              inputTokensLimit! > 0 &&
              inputTokensRemaining != null)
          ? inputTokensRemaining! / inputTokensLimit!
          : 1.0;

  double get outputTokensPercent =>
      (outputTokensLimit != null &&
              outputTokensLimit! > 0 &&
              outputTokensRemaining != null)
          ? outputTokensRemaining! / outputTokensLimit!
          : 1.0;

  factory RateLimits.fromJson(Map<String, dynamic> json) => RateLimits(
        requestsLimit: json['requests-limit'] as int?,
        requestsRemaining: json['requests-remaining'] as int?,
        requestsReset: json['requests-reset'] as String?,
        inputTokensLimit: json['input-tokens-limit'] as int?,
        inputTokensRemaining: json['input-tokens-remaining'] as int?,
        inputTokensReset: json['input-tokens-reset'] as String?,
        outputTokensLimit: json['output-tokens-limit'] as int?,
        outputTokensRemaining: json['output-tokens-remaining'] as int?,
        outputTokensReset: json['output-tokens-reset'] as String?,
      );
}
