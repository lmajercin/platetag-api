<?php

namespace App\Observers;

use App\Models\Plate;
use Illuminate\Support\Facades\DB;

class PlateObserver
{
    /**
     * When a plate is saved with is_primary = true, clear that flag
     * from every other plate in the same series_id so only one primary
     * exists per series at a time.
     */
    public function saving(Plate $plate): void
    {
        if ($plate->is_primary && $plate->isDirty('is_primary')) {
            // Clear is_primary from all other plates in this series
            DB::table('plates')
                ->where('series_id', $plate->series_id)
                ->where('id', '!=', $plate->id ?? 0)
                ->update(['is_primary' => false]);

            // A plate cannot be both primary and secondary — clear secondary on this plate
            $plate->is_secondary = false;
        }
    }

    public function created(Plate $plate): void {}
    public function updated(Plate $plate): void {}
    public function deleted(Plate $plate): void {}
    public function restored(Plate $plate): void {}
    public function forceDeleted(Plate $plate): void {}
}
