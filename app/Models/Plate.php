<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

class Plate extends Model
{
    protected $fillable = [
        'state_code',
        'country_code',
        'plate_type',
        'name',
        'slug',
        'image_filename',
        'year_introduced',
        'year_discontinued',
        'is_active',
    ];

    protected $casts = [
        'is_active'         => 'boolean',
        'year_introduced'   => 'integer',
        'year_discontinued' => 'integer',
    ];

    public function discoveredBy(): BelongsToMany
    {
        return $this->belongsToMany(User::class, 'user_discovered_plates')
            ->withPivot('discovered_at', 'notes')
            ->withTimestamps();
    }
}
