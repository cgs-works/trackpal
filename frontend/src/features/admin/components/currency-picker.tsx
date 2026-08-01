import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Search, ChevronDown, Check, Coins } from "lucide-react";
import { cn } from "@/lib/utils";
import { t } from "@/i18n";

interface CurrencyOption {
  code: string;
  symbol: string;
  minor_units: number;
}

interface CurrencyPickerProps {
  value: string | null;
  currencies: CurrencyOption[];
  officialCurrency: string | null;
  onChange: (code: string | null) => void;
  error?: boolean;
}

export function CurrencyPicker({
  value,
  currencies,
  officialCurrency,
  onChange,
  error,
}: CurrencyPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });

  const { official, rest } = useMemo(() => {
    if (!officialCurrency) return { official: null, rest: currencies };
    return {
      official: currencies.find((c) => c.code === officialCurrency) ?? null,
      rest: currencies.filter((c) => c.code !== officialCurrency),
    };
  }, [currencies, officialCurrency]);

  const allFiltered = useMemo(() => {
    const items = official ? [official, ...rest] : rest;
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.symbol.toLowerCase().includes(q)
    );
  }, [official, rest, search]);

  const selected = currencies.find((c) => c.code === value);

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
      const dropdown = document.getElementById("currency-picker-dropdown");
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

  function renderOption(c: CurrencyOption) {
    return (
      <button
        key={c.code}
        type="button"
        role="option"
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
        <span>
          {c.code} · {c.symbol}
        </span>
        {value === c.code && <Check className="h-4 w-4 text-primary" />}
      </button>
    );
  }

  const showGrouping = official && officialCurrency && !search;
  const filteredOfficial = showGrouping && official && allFiltered.includes(official)
    ? official
    : null;
  const filteredRest = allFiltered.filter((c) => c !== filteredOfficial);

  const dropdown = isOpen
    ? createPortal(
        <div
          id="currency-picker-dropdown"
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
                placeholder="Search currency..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              />
            </div>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: "260px" }}>
            {allFiltered.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No currencies found
              </div>
            ) : (
              <>
                {showGrouping && filteredOfficial && (
                  <>
                    <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground bg-muted/50">
                      {t("frontend.my_account.regional.country_currency_group")}
                    </div>
                    {renderOption(filteredOfficial)}
                  </>
                )}
                {showGrouping && filteredOfficial && filteredRest.length > 0 && (
                  <Separator />
                )}
                {showGrouping && filteredOfficial ? (
                  filteredRest.map(renderOption)
                ) : (
                  allFiltered.map(renderOption)
                )}
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
          <Coins className="h-4 w-4 shrink-0 opacity-50" />
          <span className="truncate">
            {selected ? `${selected.code} · ${selected.symbol}` : "Select currency"}
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
