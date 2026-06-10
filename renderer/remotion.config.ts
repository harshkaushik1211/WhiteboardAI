import { Config } from "@remotion/cli/config";

// PNG keeps thin whiteboard lines sharp (JPEG greys out incomplete strokes).
Config.setVideoImageFormat("png");
Config.setOverwriteOutput(true);
