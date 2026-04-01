<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Series extends Model
{
    protected $fillable = [
        'name', 'slug', 'region_id', 'country_code',
        'background', 'header', 'footer', 'digits_style',
        'year_start', 'year_end', 'notes', 'image_filename', 'is_active',
    ];

    protected $casts = [
        'is_active'  => 'boolean',
        'year_start' => 'integer',
        'year_end'   => 'integer',
    ];

    public function region(): BelongsTo
    {
        return $this->belongsTo(Region::class);
    }

    public function plates(): HasMany
    {
        return $this->hasMany(Plate::class);
    }
}
