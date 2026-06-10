"use client";

import { Download, Maximize2 } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

interface VideoPreviewProps {
  videoUrl: string;
  title?: string;
}

export function VideoPreview({ videoUrl, title }: VideoPreviewProps) {
  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = videoUrl;
    a.download = `${title || "whiteboard-video"}.mp4`;
    a.click();
  };

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{title || "Your Video"}</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
        </div>
      </div>
      <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
        <video
          src={videoUrl}
          controls
          className="w-full h-full"
          playsInline
        />
      </div>
    </Card>
  );
}
