import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface OptionButtonProps {
  children: React.ReactNode;
  onClick: () => void;
  variant?: "default" | "outline" | "success";
  className?: string;
  disabled?: boolean;
}

export function OptionButton({ 
  children, 
  onClick, 
  variant = "outline", 
  className,
  disabled = false 
}: OptionButtonProps) {
  const [isPressed, setIsPressed] = useState(false);

  const handleClick = () => {
    setIsPressed(true);
    onClick();
    // Reset pressed state after a short delay to show feedback
    setTimeout(() => setIsPressed(false), 150);
  };

  return (
    <Button
      onClick={handleClick}
      disabled={disabled}
      variant={variant === "success" ? "default" : variant}
      className={cn(
        "w-full justify-start text-left py-3 px-4 h-auto font-normal font-sans text-sm border-border transition-all duration-200",
        // Delicate shadow
        "shadow-sm hover:shadow-md",
        // Normal state
        "hover:bg-muted/50",
        // Pressed state with blue background and white text (matching button style)
        isPressed && "bg-blue-500 text-white border-blue-500",
        // Success variant
        variant === "success" && "bg-primary hover:bg-primary/90 text-primary-foreground border-primary",
        className
      )}
    >
      <span>{children}</span>
    </Button>
  );
}