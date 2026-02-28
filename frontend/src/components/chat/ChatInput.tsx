"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, ImagePlus, X, Loader2 } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useConnectionStore } from "@/stores/useConnectionStore";
import { useToastStore } from "@/stores/useToastStore";
import { useTranslation } from "@/hooks/useTranslation";
import { uploadImages } from "@/lib/api";
import type { ImageAttachment } from "@/lib/types";

const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
const MAX_IMAGES = 10;
const MAX_IMAGE_SIZE = 20 * 1024 * 1024; // 20MB

export default function ChatInput() {
  const [text, setText] = useState("");
  const [images, setImages] = useState<ImageAttachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const agents = useAgentStore((s) => s.agents);
  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const appendMessage = useAgentStore((s) => s.appendMessage);
  const setProcessing = useAgentStore((s) => s.setProcessing);
  const setAgentStatus = useAgentStore((s) => s.setAgentStatus);
  const send = useConnectionStore((s) => s.send);
  const authToken = useConnectionStore((s) => s.authToken);
  const { t } = useTranslation();
  const [isUploading, setIsUploading] = useState(false);

  const activeAgent = activeAgentId ? agents[activeAgentId] : null;
  const isProcessing = activeAgent?.isProcessing || false;
  const hasCwd = !!activeAgent?.cwd;

  const isDisabled = isProcessing || !hasCwd;

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.min(el.scrollHeight, 200);
    el.style.height = newHeight + "px";
    el.style.overflowY = el.scrollHeight > 200 ? "auto" : "hidden";
  };

  useEffect(() => {
    adjustHeight();
  }, [text]);

  // Scroll textarea into view when mobile keyboard opens
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const handleResize = () => {
      textareaRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    vv.addEventListener("resize", handleResize);
    return () => vv.removeEventListener("resize", handleResize);
  }, []);

  /** Convert a File to base64 ImageAttachment */
  const fileToImageAttachment = useCallback((file: File): Promise<ImageAttachment | null> => {
    return new Promise((resolve) => {
      if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
        resolve(null);
        return;
      }
      if (file.size > MAX_IMAGE_SIZE) {
        useToastStore.getState().addToast({
          type: "error",
          message: `Image too large (max 20MB): ${file.name}`,
        });
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        // Strip "data:image/png;base64," prefix
        const base64 = dataUrl.split(",")[1];
        resolve({ file, base64, mediaType: file.type });
      };
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(file);
    });
  }, []);

  /** Handle files from input or drop */
  const processFiles = useCallback(async (files: FileList | File[]) => {
    const remaining = MAX_IMAGES - images.length;
    if (remaining <= 0) {
      useToastStore.getState().addToast({
        type: "error",
        message: `Maximum ${MAX_IMAGES} images`,
      });
      return;
    }
    const fileArr = Array.from(files).slice(0, remaining);
    const results = await Promise.all(fileArr.map(fileToImageAttachment));
    const valid = results.filter((r): r is ImageAttachment => r !== null);
    if (valid.length > 0) {
      setImages((prev) => [...prev, ...valid]);
    }
  }, [images.length, fileToImageAttachment]);

  /** Handle paste event — intercept images from clipboard */
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault();
      processFiles(imageFiles);
    }
  }, [processFiles]);

  /** Handle drag & drop */
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer?.files) {
      const imageFiles = Array.from(e.dataTransfer.files).filter((f) =>
        f.type.startsWith("image/")
      );
      if (imageFiles.length > 0) processFiles(imageFiles);
    }
  }, [processFiles]);

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = async () => {
    const trimmed = text.trim();
    if ((!trimmed && images.length === 0) || !activeAgentId || !hasCwd || isProcessing || isUploading) return;

    const currentImages = [...images];

    // Clear input immediately for responsive UX
    setText("");
    setImages([]);

    // Show optimistic user message
    appendMessage(activeAgentId, {
      id: crypto.randomUUID(),
      type: "user",
      text: trimmed,
      timestamp: Date.now(),
      animate: true,
      ...(currentImages.length > 0 ? { images: currentImages } : {}),
    });
    setProcessing(activeAgentId, true);
    setAgentStatus(activeAgentId, "working");

    // Upload images via HTTP if present
    let imageIds: string[] | undefined;
    const filesToUpload = currentImages.filter((img) => img.file).map((img) => img.file!);
    if (filesToUpload.length > 0) {
      setIsUploading(true);
      try {
        imageIds = await uploadImages(filesToUpload, authToken);
        if (imageIds.length === 0) {
          useToastStore.getState().addToast({ type: "error", message: t("toast.sendFailed") });
          setProcessing(activeAgentId, false);
          setAgentStatus(activeAgentId, "idle");
          setIsUploading(false);
          return;
        }
      } catch {
        useToastStore.getState().addToast({ type: "error", message: t("toast.sendFailed") });
        setProcessing(activeAgentId, false);
        setAgentStatus(activeAgentId, "idle");
        setIsUploading(false);
        return;
      }
      setIsUploading(false);
    }

    const sent = send({
      type: "send_message",
      text: trimmed,
      agent_id: activeAgentId,
      ...(imageIds && imageIds.length > 0 ? { image_ids: imageIds } : {}),
    });

    if (!sent) {
      appendMessage(activeAgentId, {
        id: crypto.randomUUID(),
        type: "system",
        text: t("chat.sendError"),
        timestamp: Date.now(),
        animate: true,
      });
      useToastStore.getState().addToast({ type: "error", message: t("toast.sendFailed") });
      setProcessing(activeAgentId, false);
      setAgentStatus(activeAgentId, "idle");
    }

    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="flex flex-col gap-2"
      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
      onDrop={handleDrop}
    >
      {/* Image preview strip */}
      {images.length > 0 && (
        <div className="flex gap-2 px-1 overflow-x-auto pb-1">
          {images.map((img, idx) => (
            <div key={idx} className="relative shrink-0 group">
              <img
                src={`data:${img.mediaType};base64,${img.base64}`}
                alt={`Attachment ${idx + 1}`}
                className="w-16 h-16 object-cover rounded-lg border border-overlay"
              />
              <button
                onClick={() => removeImage(idx)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 flex items-center justify-center rounded-full bg-red text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red/90"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        {/* Image picker button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isDisabled || images.length >= MAX_IMAGES}
          className="min-w-[44px] min-h-[44px] w-12 h-12 flex items-center justify-center rounded-xl text-subtext hover:text-primary hover:bg-surface2/70 active:scale-[0.95] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          aria-label="Attach image"
        >
          <ImagePlus size={20} />
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) processFiles(e.target.files);
            e.target.value = "";
          }}
        />

        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={t("chat.inputPlaceholder")}
          disabled={isDisabled}
          enterKeyHint="send"
          autoComplete="off"
          className={`flex-1 bg-surface2/60 text-text border border-transparent rounded-2xl px-4 py-3 text-base sm:text-sm min-h-[48px] max-h-[200px] resize-none overflow-y-hidden placeholder:text-subtext focus-ring focus:border-primary/40 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed`}
        />
        <button
          onClick={handleSend}
          disabled={(!text.trim() && images.length === 0) || isProcessing || isUploading || !hasCwd}
          className="min-w-[44px] min-h-[44px] w-12 h-12 flex items-center justify-center rounded-xl bg-primary text-on-primary transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-dark hover:shadow-[0_0_12px_rgba(var(--primary-rgb),0.3)] active:scale-[0.95] shrink-0"
        >
          {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
