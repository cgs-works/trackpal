import { useState, useMemo, useRef, useEffect } from "react";
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
  const dropdownRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
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

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-popover border rounded-lg shadow-lg overflow-hidden">
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

          <div className="max-h-[240px] overflow-y-auto">
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
        </div>
      )}
    </div>
  );
}
