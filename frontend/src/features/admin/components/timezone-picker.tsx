import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Search, ChevronDown, Check, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimezoneOption {
  value: string;
  label: string;
  group?: string;
}

interface TimezonePickerProps {
  value: string;
  onChange: (value: string) => void;
  timezones: TimezoneOption[];
  error?: boolean;
}

export function TimezonePicker({
  value,
  onChange,
  timezones,
  error,
}: TimezonePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });

  const selectedTimezone = timezones.find((tz) => tz.value === value);
  const selectedLabel = selectedTimezone
    ? `${selectedTimezone.label} (${selectedTimezone.value})`
    : value || "Select timezone";

  const filteredTimezones = useMemo(() => {
    if (!search) return timezones;
    const query = search.toLowerCase();
    return timezones.filter(
      (tz) =>
        tz.label.toLowerCase().includes(query) ||
        tz.value.toLowerCase().includes(query)
    );
  }, [timezones, search]);

  const updatePosition = useCallback(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
        width: rect.width,
      });
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    function handleScroll() {
      updatePosition();
    }
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      // Check if click is inside the trigger or the portal dropdown
      if (
        containerRef.current &&
        containerRef.current.contains(target)
      ) {
        return;
      }
      const dropdown = document.getElementById("tz-picker-dropdown");
      if (dropdown && dropdown.contains(target)) {
        return;
      }
      setIsOpen(false);
      setSearch("");
    }
    window.addEventListener("scroll", handleScroll, true);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      window.removeEventListener("scroll", handleScroll, true);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, updatePosition]);

  const dropdown = isOpen
    ? createPortal(
        <div
          id="tz-picker-dropdown"
          className="fixed z-[9999] bg-popover border rounded-lg shadow-xl overflow-hidden"
          style={{
            top: dropdownPos.top,
            left: dropdownPos.left,
            width: dropdownPos.width,
            maxHeight: "320px",
          }}
        >
          <div className="p-2 border-b">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Search timezone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              />
            </div>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: "260px" }}>
            {filteredTimezones.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No timezones found
              </div>
            ) : (
              filteredTimezones.map((tz) => (
                <button
                  key={tz.value}
                  type="button"
                  className={cn(
                    "w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors flex items-center justify-between",
                    value === tz.value && "bg-accent"
                  )}
                  onClick={() => {
                    onChange(tz.value);
                    setIsOpen(false);
                    setSearch("");
                  }}
                >
                  <span className="flex flex-col">
                    <span className="font-medium">{tz.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {tz.value}
                    </span>
                  </span>
                  {value === tz.value && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </button>
              ))
            )}
          </div>

          <Separator />
          <div className="p-2">
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-start text-sm h-8"
              onClick={() => {
                onChange("UTC");
                setIsOpen(false);
                setSearch("");
              }}
            >
              <span className="mr-2">🕐</span>
              UTC (Coordinated Universal Time)
              {value === "UTC" && (
                <Check className="h-4 w-4 text-primary ml-auto" />
              )}
            </Button>
          </div>
        </div>,
        document.body
      )
    : null;

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant="outline"
        className={cn(
          "w-full justify-between h-auto min-h-[40px] py-2 font-normal",
          error && "border-destructive",
          !value && "text-muted-foreground"
        )}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="flex items-center gap-2 truncate">
          <Globe className="h-4 w-4 shrink-0 opacity-50" />
          <span className="truncate">{selectedLabel}</span>
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 opacity-50 transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </Button>

      {dropdown}
    </div>
  );
}
