import React from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export function Pagination({
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  pageSize = 10,
  totalItems,
  onPageSizeChange,
  className,
}) {
  return (
    <div className={cn('flex flex-col sm:flex-row items-center justify-between gap-4 py-3 text-xs text-gray-400 font-sans', className)}>
      {totalItems !== undefined && (
        <div>
          Showing <span className="font-semibold text-white">{Math.min((currentPage - 1) * pageSize + 1, totalItems)}</span> to{' '}
          <span className="font-semibold text-white">{Math.min(currentPage * pageSize, totalItems)}</span> of{' '}
          <span className="font-semibold text-white">{totalItems}</span> entries
        </div>
      )}

      <div className="flex items-center gap-2 ml-auto">
        {onPageSizeChange && (
          <div className="flex items-center gap-2 mr-4">
            <span>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="bg-gray-900 border border-gray-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              {[10, 25, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(1)}
            disabled={currentPage <= 1}
            aria-label="First Page"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Previous Page"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-3 py-1 rounded-lg bg-gray-900 border border-gray-800 font-semibold text-white">
            {currentPage} / {Math.max(1, totalPages)}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            aria-label="Next Page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(totalPages)}
            disabled={currentPage >= totalPages}
            aria-label="Last Page"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
