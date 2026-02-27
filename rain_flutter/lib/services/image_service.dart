import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// Uploads images via HTTP and returns server-issued reference IDs.
class ImageService {
  final Dio _dio;

  ImageService(this._dio);

  /// Upload a single image. Returns the image_id on success.
  Future<String> uploadImage(
    Uint8List bytes,
    String mediaType,
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'image': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(mediaType),
      ),
    });

    final response = await _dio.post(
      '/upload-image',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    if (response.statusCode == 200 && response.data is Map) {
      return response.data['image_id'] as String;
    }

    throw Exception('Image upload failed: ${response.statusCode}');
  }

  /// Upload multiple images. Returns list of image_ids (skips failures).
  Future<List<String>> uploadImages(
    List<({Uint8List bytes, String mediaType, String filename})> images,
  ) async {
    final results = <String>[];
    for (final img in images) {
      try {
        final id = await uploadImage(img.bytes, img.mediaType, img.filename);
        results.add(id);
      } catch (e) {
        debugPrint('[ImageService] Upload failed: $e');
      }
    }
    return results;
  }
}
