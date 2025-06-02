Starting April 29, 2025, Gemini 1.5 Pro and Gemini 1.5 Flash models are not
available in projects that have no prior usage of these models, including new
projects. For details, see Model versions and lifecycle. Generative AI on Vertex
AI Documentation Was this helpful?

Send feedbackGemini 2.5 Pro

bookmark_border Release Notes Preview

This feature is subject to the "Pre-GA Offerings Terms" in the General Service
Terms section of the Service Specific Terms. Pre-GA features are available "as
is" and might have limited support. For more information, see the launch stage
descriptions.

Gemini 2.5 Pro is our most advanced reasoning Gemini model, capable of solving
complex problems.

Try in Vertex AI View model card in Model Garden (Preview) Deploy example app

Note: To use the "Deploy example app" feature, you need a Google Cloud project
with billing and Vertex AI API enabled. Model ID	gemini-2.5-pro-preview-05-06
Supported inputs & outputs Inputs: Text, Code, Images, Audio, Video Outputs:
Text Token limits Maximum input tokens: 1,048,576 Maximum output tokens: 65,535
Capabilities Supported Grounding with Google Search Code execution System
instructions Controlled generation Function calling Count Tokens Thinking
preview Context caching Vertex AI RAG Engine Chat completions Not supported
Tuning Batch prediction Live API preview Usage types Supported Provisioned
Throughput Dynamic shared quota Not supported Fixed quota Technical
specifications Images Maximum images per prompt: 3,000 Maximum image size: 7 MB
Supported MIME types: image/png, image/jpeg, image/webp Documents Maximum number
of files per prompt: 3,000 Maximum number of pages per file: 1,000 Maximum file
size per file: 50 MB Supported MIME types: application/pdf, text/plain Video
Maximum video length (with audio): Approximately 45 minutes Maximum video length
(without audio): Approximately 1 hour Maximum number of videos per prompt: 10
Supported MIME types: video/x-flv, video/quicktime, video/mpeg, video/mpegs,
video/mpg, video/mp4, video/webm, video/wmv, video/3gpp Audio Maximum audio
length per prompt: Appropximately 8.4 hours, or up to 1 million tokens Maximum
number of audio files per prompt: 1 Speech understanding for: Audio
summarization, transcription, and translation Supported MIME types: audio/x-aac,
audio/flac, audio/mp3, audio/m4a, audio/mpeg, audio/mpga, audio/mp4, audio/opus,
audio/pcm, audio/wav, audio/webm Parameter defaults Temperature: 0-2 topP: 0.95
topK: 64 (fixed) candidateCount: 1-8 Knowledge cutoff date	January 2025 Versions
gemini-2.5-pro-preview-05-06 Launch stage: Public preview Release date: May 6,
2025 gemini-2.5-pro-exp-03-25 Launch stage: Experimental Release date: March 28,
2025 Supported regions Model availability

Global global

United States us-central1 See Data residency for more information. Security
controls See Security controls for more information. Pricing	See Pricing.
