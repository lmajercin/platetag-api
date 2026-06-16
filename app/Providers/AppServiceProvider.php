<?php

namespace App\Providers;

use App\Models\Plate;
use App\Observers\PlateObserver;
use Illuminate\Support\ServiceProvider;
use Illuminate\Support\Facades\Schema;
use Jeffgreco13\FilamentBreezy\Livewire\TwoFactorAuthentication;
use Livewire\Livewire;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        Schema::defaultStringLength(191);
        Plate::observe(PlateObserver::class);
        Livewire::component('two_factor_authentication', TwoFactorAuthentication::class);
    }
}
