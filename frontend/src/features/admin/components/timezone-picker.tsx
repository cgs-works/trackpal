import { useState, useMemo, useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Search, ChevronDown, Check, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimezoneOption {
  value: string;
  label: string;
  group: string;
}

interface TimezonePickerProps {
  value: string;
  onChange: (value: string) => void;
  timezones: TimezoneOption[];
  error?: boolean;
}

// Continent icons/labels
const CONTINENTS: Record<string, { label: string; emoji: string }> = {
  America: { label: "America", emoji: "🌎" },
  Europe: { label: "Europe", emoji: "🌍" },
  Asia: { label: "Asia", emoji: "🌏" },
  Africa: { label: "Africa", emoji: "🌍" },
  Australia: { label: "Australia", emoji: "🌏" },
  Pacific: { label: "Pacific", emoji: "🌏" },
  Atlantic: { label: "Atlantic", emoji: "🌊" },
  Indian: { label: "Indian", emoji: "🌊" },
  Arctic: { label: "Arctic", emoji: "❄️" },
  Etc: { label: "Other", emoji: "🌐" },
  UTC: { label: "UTC", emoji: "🕐" },
};

function getContinent(group: string): string {
  if (!group) return "Other";
  if (group === "UTC") return "UTC";
  // Extract continent from group like "America/Argentina" -> "America"
  const parts = group.split("/");
  return parts[0] || "Other";
}

export function TimezonePicker({
  value,
  onChange,
  timezones,
  error,
}: TimezonePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeContinent, setActiveContinent] = useState<string>("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Get selected timezone label
  const selectedTimezone = timezones.find((tz) => tz.value === value);
  const selectedLabel = selectedTimezone
    ? `${selectedTimezone.label} (${selectedTimezone.value})`
    : value || "Select timezone";

  // Get unique continents from timezones
  const availableContinents = useMemo(() => {
    const continents = new Set<string>();
    timezones.forEach((tz) => {
      continents.add(getContinent(tz.group));
    });
    return Array.from(continents).sort();
  }, [timezones]);

  // Filter timezones based on search and active continent
  const filteredTimezones = useMemo(() => {
    let result = timezones;

    // Filter by continent if selected
    if (activeContinent) {
      result = result.filter(
        (tz) => getContinent(tz.group) === activeContinent
      );
    }

    // Filter by search query
    if (search) {
      const query = search.toLowerCase();
      result = result.filter(
        (tz) =>
          tz.label.toLowerCase().includes(query) ||
          tz.value.toLowerCase().includes(query) ||
          tz.group.toLowerCase().includes(query)
      );
    }

    return result;
  }, [timezones, search, activeContinent]);

  // Group filtered timezones by continent
  const groupedTimezones = useMemo(() => {
    const groups: Record<string, TimezoneOption[]> = {};
    filteredTimezones.forEach((tz) => {
      const continent = getContinent(tz.group);
      if (!groups[continent]) groups[continent] = [];
      groups[continent].push(tz);
    });
    return groups;
  }, [filteredTimezones]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Close dropdown when clicking outside
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

  // Set initial active continent based on selected value
  useEffect(() => {
    if (value && !activeContinent) {
      const selected = timezones.find((tz) => tz.value === value);
      if (selected) {
        setActiveContinent(getContinent(selected.group));
      }
    }
  }, [value, timezones, activeContinent]);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
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

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-popover border rounded-lg shadow-lg overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                ref={searchInputRef}
                placeholder="Search timezone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 pl-8 text-sm"
              />
            </div>
          </div>

          {/* Continent tabs */}
          <div className="flex flex-wrap gap-1 p-2 border-b bg-muted/30">
            <Button
              type="button"
              variant={activeContinent === "" ? "default" : "ghost"}
              size="sm"
              className="h-6 text-xs px-2"
              onClick={() => setActiveContinent("")}
            >
              All
            </Button>
            {availableContinents.map((continent) => {
              const info = CONTINENTS[continent] || {
                label: continent,
                emoji: "🌐",
              };
              return (
                <Button
                  key={continent}
                  type="button"
                  variant={activeContinent === continent ? "default" : "ghost"}
                  size="sm"
                  className="h-6 text-xs px-2"
                  onClick={() => setActiveContinent(continent)}
                >
                  <span className="mr-1">{info.emoji}</span>
                  {info.label}
                </Button>
              );
            })}
          </div>

          {/* Timezone list */}
          <div className="max-h-[240px] overflow-y-auto">
            {Object.keys(groupedTimezones).length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No timezones found
              </div>
            ) : (
              Object.entries(groupedTimezones).map(([continent, tzs]) => {
                const info = CONTINENTS[continent] || {
                  label: continent,
                  emoji: "🌐",
                };
                return (
                  <div key={continent}>
                    {/* Continent header */}
                    <div className="px-2 py-1.5 bg-muted/50 text-xs font-medium text-muted-foreground sticky top-0">
                      <span className="mr-1">{info.emoji}</span>
                      {info.label}
                    </div>

                    {/* Timezone items */}
                    {tzs.map((tz) => (
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
                    ))}
                  </div>
                );
              })
            )}
          </div>

          {/* UTC shortcut */}
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
