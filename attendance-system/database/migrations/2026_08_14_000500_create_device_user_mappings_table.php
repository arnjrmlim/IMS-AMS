<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Device user mappings.
 *
 * Maps a biometric device user (device_user_id from SpeedFace) to an
 * application Employee record. The mapping is optional — unmapped users
 * are retained and their attendance records are NEVER discarded.
 *
 * IMPORTANT: device_user_id is a string from the device, NOT assumed to
 * equal the employee's employee_number or any application ID.
 *
 * Unique constraint: one mapping per device per device_user_id.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('device_user_mappings', function (Blueprint $table) {
            $table->id();
            $table->foreignId('device_id')->constrained()->cascadeOnDelete();
            $table->string('device_user_id', 50);  // user id from SpeedFace
            $table->foreignId('employee_id')->nullable()->constrained()->nullOnDelete();
            $table->string('device_name', 120)->nullable(); // cached name from device
            $table->string('mapping_status', 20)->default('unmapped')->index(); // unmapped, mapped, ignored
            $table->timestamps();

            // Prevent duplicate mappings per device+user combination
            $table->unique(['device_id', 'device_user_id'], 'unique_device_user');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('device_user_mappings');
    }
};
