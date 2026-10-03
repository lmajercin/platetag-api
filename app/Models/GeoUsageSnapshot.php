<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class GeoUsageSnapshot extends Model
{
    protected $fillable = [
        'snapshot_date',
        'discoveries_total',
        'discoveries_with_location',
        'discoveries_without_location',
        'active_users',
        'users_with_location',
        'users_without_location',
        'pct_discoveries_with_location',
        'pct_users_with_location',
    ];

    protected function casts(): array
    {
        return [
            'snapshot_date' => 'date',
            'pct_discoveries_with_location' => 'float',
            'pct_users_with_location' => 'float',
        ];
    }
}
