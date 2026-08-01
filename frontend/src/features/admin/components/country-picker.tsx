import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Search, ChevronDown, Check, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { getLocale } from "@/i18n";

interface CountryOption {
  code: string;
  currency: string;
}

interface CountryPickerProps {
  value: string | null;
  countries: CountryOption[];
  onChange: (code: string | null) => void;
  error?: boolean;
}

export function CountryPicker({
  value,
  countries,
  onChange,
  error,
}: CountryPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });

  const displayNameOf = useMemo(() => {
    try {
      return new Intl.DisplayNames([getLocale()], { type: "region" });
    } catch {
      return null;
    }
  }, []);

  const labels = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of countries) {
      const name = displayNameOf?.of(c.code) ?? c.code;
      map.set(c.code, `${name} (${c.code})`);
    }
    return map;
  }, [countries, displayNameOf]);

  const selectedLabel = value ? (labels.get(value) ?? value) : null;

  const filtered = useMemo(() => {
    if (!search) return countries;
    const q = search.toLowerCase();
    return countries.filter((c) => {
      const label = labels.get(c.code) ?? c.code;
      return label.toLowerCase().includes(q) || c.code.toLowerCase().includes(q);
    });
  }, [countries, search, labels]);

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
      if (containerRef.current && containerRef.current.contains(target)) return;
      const dropdown = document.getElementById("country-picker-dropdown");
      if (dropdown && dropdown.contains(target)) return;
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
          id="country-picker-dropdown"
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
                placeholder="Search country..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              />
            </div>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: "260px" }}>
            {filtered.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No countries found
              </div>
            ) : (
              <>
                <button
                  type="button"
                  className={cn(
                    "w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors flex items-center justify-between",
                    value === null && "bg-accent"
                  )}
                  onClick={() => {
                    onChange(null);
                    setIsOpen(false);
                    setSearch("");
                  }}
                >
                  <span className="text-muted-foreground">— None —</span>
                  {value === null && <Check className="h-4 w-4 text-primary" />}
                </button>
                {filtered.map((c) => (
                  <button
                    key={c.code}
                    type="button"
                    className={cn(
                      "w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors flex items-center justify-between",
                      value === c.code && "bg-accent"
                    )}
                    onClick={() => {
                      onChange(c.code);
                      setIsOpen(false);
                      setSearch("");
                    }}
                  >
                    <span className="flex items-center gap-2">
                      <span>🌍</span>
                      <span>{labels.get(c.code) ?? c.code}</span>
                    </span>
                    {value === c.code && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </button>
                ))}
              </>
            )}
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
          <span className="truncate">
            {selectedLabel ?? "Select country"}
          </span>
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
