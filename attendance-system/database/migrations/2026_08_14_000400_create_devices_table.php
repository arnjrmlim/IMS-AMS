<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Devices table — local representation of registered SpeedFace devices.
 *
 * The source of truth for device data is the Python Integration Service.
 * This table stores a local copy for display and relational purposes.
 * The Laravel app never communicates directly with port 4370.
 *
 * speedface_device_id: the 'id' from the Python API's /api/device endpoint.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('devices', function (Blueprint $table) {
            $table->id();
            $table->foreignId('branch_id')->nullable()->constrained()->nullOnDelete();
            $table->unsignedInteger('speedface_device_id')->nullable()->unique(); // id from Python API
            $table->string('name', 120)->nullable();
            $table->string('model', 80)->nullable();
            $table->string('serial_number', 80)->nullable()->unique();
            $table->string('ip_address', 45)->nullable();
            $table->unsignedSmallInteger('port')->default(4370);
            $table->string('firmware_version', 80)->nullable();
            $table->string('platform', 80)->nullable();
            $table->unsignedInteger('user_count')->nullable();
            $table->unsignedInteger('attendance_count')->nullable();
            $table->string('status', 20)->default('unknown')->index(); // online, offline, unknown
            $table->timestamp('last_connected_at')->nullable();
            $table->timestamp('last_sync_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('devices');
    }
};
