<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Models\Device;
use Illuminate\Database\Eloquent\Factories\Factory;

/** @extends Factory<Device> */
class DeviceFactory extends Factory
{
    public function definition(): array
    {
        return [
            'speedface_device_id' => fake()->unique()->randomNumber(3),
            'name'                => 'SpeedFace-V5L Test',
            'model'               => 'xFace600',
            'serial_number'       => fake()->unique()->bothify('SF###??###'),
            'ip_address'          => fake()->localIpv4(),
            'port'                => 4370,
            'firmware_version'    => 'Ver 6.60 Aug 28 2020',
            'platform'            => 'ZAM180_TFT',
            'status'              => 'online',
        ];
    }
}
