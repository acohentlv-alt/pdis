import { useState, useEffect } from 'react';

interface ImageViewerProps {
  images: string[];
  startIndex?: number;
  onClose: () => void;
}

export default function ImageViewer({ images, startIndex = 0, onClose }: ImageViewerProps) {
  const [index, setIndex] = useState(startIndex);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') setIndex(i => Math.min(i + 1, images.length - 1));
      if (e.key === 'ArrowLeft') setIndex(i => Math.max(i - 1, 0));
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [images.length, onClose]);

  if (images.length === 0) return null;

  return (
    <div
      className="fixed inset-0 bg-black/90 z-[100] flex flex-col"
      onClick={onClose}
    >
      {/* Close button */}
      <div className="flex justify-between items-center px-4 py-3">
        <span className="text-white text-sm">{index + 1} / {images.length}</span>
        <button
          onClick={onClose}
          className="text-white text-2xl font-bold w-10 h-10 flex items-center justify-center"
        >
          ✕
        </button>
      </div>

      {/* Main image */}
      <div
        className="flex-1 flex items-center justify-center px-4"
        onClick={e => e.stopPropagation()}
      >
        {index > 0 && (
          <button
            onClick={() => setIndex(i => i - 1)}
            className="text-white text-4xl px-2 py-8 opacity-70 hover:opacity-100"
          >
            ‹
          </button>
        )}
        <img
          src={images[index]}
          alt=""
          className="max-h-[75vh] max-w-full object-contain rounded-lg"
        />
        {index < images.length - 1 && (
          <button
            onClick={() => setIndex(i => i + 1)}
            className="text-white text-4xl px-2 py-8 opacity-70 hover:opacity-100"
          >
            ›
          </button>
        )}
      </div>

      {/* Thumbnail strip */}
      {images.length > 1 && (
        <div
          className="flex gap-2 overflow-x-auto px-4 py-3 justify-center"
          onClick={e => e.stopPropagation()}
        >
          {images.map((url, i) => (
            <img
              key={i}
              src={url}
              alt=""
              onClick={() => setIndex(i)}
              className={`h-14 w-20 object-cover rounded cursor-pointer shrink-0 transition-opacity ${
                i === index ? 'opacity-100 ring-2 ring-white' : 'opacity-50'
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
