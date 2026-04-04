<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Support\Facades\Storage;

class Plate extends Model
{
    protected $appends = ['image_url'];

    protected $fillable = [
        'name', 'slug', 'series_id', 'category_id', 'vehicle_class',
        'header_override', 'footer_override', 'detail', 'serial_format',
        'image_filename', 'updates_complete', 'is_active',
    ];

    protected $casts = [
        'is_active'        => 'boolean',
        'updates_complete' => 'boolean',
    ];

    public function series(): BelongsTo
    {
        return $this->belongsTo(Series::class);
    }

    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class);
    }

    public function discoveredBy(): BelongsToMany
    {
        return $this->belongsToMany(User::class, 'user_discovered_plates')
            ->withPivot('discovered_at', 'notes')
            ->withTimestamps();
    }

    public function getImageUrlAttribute(): ?string
    {
        if (!$this->image_filename) {
            return null;
        }

        return Storage::disk('public')->url('plates/' . $this->image_filename);
    }
}
