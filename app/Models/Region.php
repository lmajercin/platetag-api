<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Region extends Model
{
    protected $fillable = [
        'name', 'code', 'country_code', 'capital_city',
        'capital_lat', 'capital_lng', 'is_active',
    ];

    protected $casts = ['is_active' => 'boolean'];
}
