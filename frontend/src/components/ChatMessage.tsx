import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: string;
  isBot?: boolean;
  emoji?: string;
  className?: string;
}

export function ChatMessage({ message, isBot = false, emoji, className }: ChatMessageProps) {
  if (isBot) {
    // Bot messages without bubbles, clean like Lovable
    return (
      <div className={cn("flex w-full mb-6 animate-fade-in", className)}>
        <div className="flex items-start space-x-3 max-w-[90%]">
          {emoji && (
            <span className="text-base mt-1 flex-shrink-0">{emoji}</span>
          )}
          <div className="text-sm text-foreground leading-relaxed font-normal font-sans">
            {message}
          </div>
        </div>
      </div>
    );
  }

  // User messages with soft beige bubbles
  return (
    <div className={cn("flex w-full mb-6 justify-end animate-fade-in", className)}>
      <div className="max-w-[75%] px-3 py-2 bg-muted text-foreground rounded-lg text-sm leading-relaxed font-normal font-sans">
        {message}
      </div>
    </div>
  );
}