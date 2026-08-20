<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * System settings — key/value configuration store.
 *
 * Stores non-sensitive application preferences such as timezone display,
 * date format, pagination defaults, and app metadata.
 *
 * IMPORTANT: Secrets (API keys, passwords, device comm keys) must NOT
 * be stored in this table. They belong in .env only.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('system_settings', function (Blueprint $table) {
            $table->id();
            $table->string('key', 80)->unique();
            $table->text('value')->nullable();
            $table->string('type', 20)->default('string'); // string, boolean, integer, json
            $table->string('group', 60)->default('general')->index();
            $table->string('label', 120)->nullable();
            $table->string('description')->nullable();
            $table->boolean('is_public')->default(false); // safe to expose to JS?
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('system_settings');
    }
};
